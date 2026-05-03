import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np


class LinearAnalytic(nn.Module):
    def __init__(self, in_d, num_classes):
        super(LinearAnalytic, self).__init__()
        self.act = nn.Identity()
        self.fc = nn.Linear(in_d, num_classes, bias=False)

    def forward(self, x):
        x_act = self.act(x)
        x_fc = self.fc(x_act)
        return x_act, x_fc


def init_local(args):
    local_model = LinearAnalytic(args.feat_size, args.num_classes).cuda()
    return local_model


def local_update(train_loader, model, global_model, args):
    corr_rep   = torch.zeros(args.feat_size, args.feat_size).cuda(args.gpu, non_blocking=True)
    corr_label = torch.zeros(args.feat_size, args.num_classes).cuda(args.gpu, non_blocking=True)

    with torch.no_grad():
        for batch_idx, (images, labels) in enumerate(train_loader):
            images = images.cuda(args.gpu, non_blocking=True)
            labels = labels.cuda(args.gpu, non_blocking=True)

            reps = model(images)
            reps, _ = global_model(reps)

            label_onehot = F.one_hot(labels, args.num_classes).float()
            corr_rep   += reps.t() @ reps
            corr_label += reps.t() @ label_onehot

        # ------------------------------------------------------------------
        # Auto-regularization guard.
        # When args.rg == 0 the correlation matrix is often rank-deficient
        # (clients have very few samples on non-IID splits), making direct
        # inversion numerically unstable or outright undefined.
        # Fall back to a data-driven ridge: mean diagonal / 1000.
        # ------------------------------------------------------------------
        if args.rg > 0:
            rg = args.rg
        else:
            rg = max(
                torch.trace(corr_rep).item() / (corr_rep.shape[0] * 1000.0),
                1e-6
            )

        # Regularised inverse  R = (X^T X + rg * I)^{-1}
        A = (corr_rep + rg * torch.eye(corr_rep.size(0), device=corr_rep.device)).double()
        R = torch.linalg.inv(A)                          # stays on GPU
        Delta = R @ corr_label.double()
        W = Delta                                        # shape: [feat_size, num_classes]

        # ------------------------------------------------------------------
        # Rank-r approximation — send factors, reconstruct on server.
        # Actual bytes transmitted for W = U(feat×r) + S(r) + Vh(r×classes)
        # instead of full W(feat×classes). Reconstruction happens here to
        # keep aggregation() interface unchanged, but comm cost is measured
        # from the factor sizes, not the reconstructed matrix size.
        # ------------------------------------------------------------------
        if args.rank_r > 0:
            r = min(args.rank_r, W.shape[0], W.shape[1])
            U, S, Vh = torch.linalg.svd(W.double(), full_matrices=False)
            # Only top-r components kept (this is what would be transmitted)
            U_r  = U[:, :r]
            S_r  = S[:r]
            Vh_r = Vh[:r, :]
            # Reconstruct for aggregation (server would do this step)
            W = (U_r @ torch.diag(S_r) @ Vh_r).double()
            # Attach actual transmitted size as metadata
            W._svd_transmitted = int(U_r.numel() + S_r.numel() + Vh_r.numel())
        else:
            W._svd_transmitted = int(W.numel())

        C = torch.linalg.inv(R).double().cpu()
        R = R.cpu()
        W = W.cpu()

    return W, R, C


def aggregation(W, R, C, args):
    """
    Exact AFL aggregation (Woodbury-based recursive merging).
    Input: lists of per-client W, R, C.
    Returns the aggregated global Wt, Rt, Ct.
    """
    if len(W) < 2:
        print("No need to aggregate")
        return (W[0].cuda(args.gpu, non_blocking=True),
                R[0].cuda(args.gpu, non_blocking=True),
                C[0].cuda(args.gpu, non_blocking=True))

    gpu_dev = f'cuda:{args.gpu}'
    eye = torch.eye(R[0].shape[0], dtype=torch.float64, device=gpu_dev)

    # Merge first two clients
    R[0] = R[0].to(gpu_dev);  C[0] = C[0].to(gpu_dev);  W[0] = W[0].to(gpu_dev)
    R[1] = R[1].to(gpu_dev);  C[1] = C[1].to(gpu_dev);  W[1] = W[1].to(gpu_dev)

    C01_inv = torch.linalg.inv(C[0] + C[1])
    Wt = ((eye - R[0] @ C[1] + R[0] @ C[1] @ C01_inv @ C[1]) @ W[0] +
          (eye - R[1] @ C[0] + R[1] @ C[0] @ C01_inv @ C[0]) @ W[1])
    Ct = C[0] + C[1]
    Rt = torch.linalg.inv(Ct)

    # Release first two from GPU to save memory
    for k in (0, 1):
        R[k] = R[k].cpu();  C[k] = C[k].cpu();  W[k] = W[k].cpu()

    # Merge remaining clients one by one
    for i in range(1, len(W) - 1):
        R[i + 1] = R[i + 1].to(gpu_dev)
        C[i + 1] = C[i + 1].to(gpu_dev)
        W[i + 1] = W[i + 1].to(gpu_dev)

        Cnew_inv = torch.linalg.inv(Ct + C[i + 1])
        Wt = ((eye - Rt @ C[i + 1] + Rt @ C[i + 1] @ Cnew_inv @ C[i + 1]) @ Wt +
              (eye - R[i + 1] @ Ct  + R[i + 1] @ Ct  @ Cnew_inv @ Ct)       @ W[i + 1])
        Ct = Ct + C[i + 1]
        Rt = torch.linalg.inv(Ct)

        R[i + 1] = R[i + 1].cpu()
        C[i + 1] = C[i + 1].cpu()
        W[i + 1] = W[i + 1].cpu()

    return Wt, Rt, Ct


def clean_regularization(W, C, args):
    """
    Remove the ridge-regularisation bias from the aggregated solution using
    the Woodbury identity (identical to the paper formulation).

    All tensors are cast to double (float64) before arithmetic to avoid
         the float32/float64 mismatch that caused a runtime error in the
         original code.
    """
    rg = args.rg if args.rg > 0 else 0.0
    if rg == 0.0:
        # Nothing to clean when no explicit regularisation was requested.
        return W

    gpu_dev = f'cuda:{args.gpu}'
    eye = torch.eye(args.feat_size, dtype=torch.float64, device=gpu_dev)

    # global X^T X = C_aggregated  - num_clients * rg * I
    # R_origin    = (global X^T X)^{-1}
    C_d = C.double().to(gpu_dev)
    R_origin = torch.linalg.inv(C_d - args.num_clients * rg * eye)

    W_d = W.double().to(gpu_dev)
    Wt  = W_d + (args.num_clients * rg * R_origin) @ W_d
    return Wt


def validate(val_loader, model, global_model, args):
    num_correct = 0
    num_sample  = 0
    model.eval()
    with torch.no_grad():
        for i, (images, target) in enumerate(val_loader):
            images = images.cuda(args.gpu, non_blocking=True)
            target = target.cuda(args.gpu, non_blocking=True)

            ref = model(images)
            _, output = global_model(ref)

            num_correct += _count_correct(output, target)
            num_sample  += images.size(0)
    return num_correct, num_sample


def _count_correct(output, target):
    with torch.no_grad():
        _, pred = output.topk(1, 1, True, True)
        pred = pred.t()
        correct = pred.eq(target.view(1, -1).expand_as(pred))
        return correct[:1].reshape(-1).float().sum(0, keepdim=False)

# COMMUNICATION COST ANALYSIS

def compute_comm_cost(feat_size, num_classes, num_clients, rank_r=0):
    BYTES = 8  # float64

    W_orig_elems = feat_size * num_classes
    C_elems      = feat_size * feat_size

    if rank_r > 0:
        r = min(rank_r, feat_size, num_classes)
        # SVD factors: U(feat×r) + S(r,) + Vh(r×classes)
        W_comp_elems   = feat_size * r + r + r * num_classes
        rank_note      = f"{rank_r} (effective = {r})"
        w_saving_pct   = (1 - W_comp_elems / W_orig_elems) * 100
    else:
        W_comp_elems   = W_orig_elems
        rank_note      = "disabled"
        w_saving_pct   = 0.0

    orig_per  = (W_orig_elems + C_elems) * BYTES
    comp_per  = (W_comp_elems + C_elems) * BYTES
    orig_tot  = orig_per * num_clients
    comp_tot  = comp_per * num_clients
    saved     = orig_tot - comp_tot
    pct       = saved / orig_tot * 100 if orig_tot > 0 else 0.0

    def mb(b): return b / 1024 ** 2

    return dict(
        feat_size          = feat_size,
        num_classes        = num_classes,
        num_clients        = num_clients,
        rank_r             = rank_note,
        W_orig_MB          = mb(W_orig_elems * BYTES),
        W_comp_MB          = mb(W_comp_elems * BYTES),
        C_MB               = mb(C_elems * BYTES),
        orig_per_client_MB = mb(orig_per),
        comp_per_client_MB = mb(comp_per),
        orig_total_MB      = mb(orig_tot),
        comp_total_MB      = mb(comp_tot),
        saving_MB          = mb(saved),
        saving_pct         = pct,
        w_saving_pct       = w_saving_pct,
        c_dominance_pct    = mb(C_elems * BYTES) / mb(orig_per) * 100,
    )


def print_comm_cost_report(s):
    sep = "=" * 62
    print(f"\n{sep}")
    print("  COMMUNICATION COST REPORT")
    print(sep)
    print(f"  Embedding size (feat)   : {s['feat_size']}")
    print(f"  Num classes             : {s['num_classes']}")
    print(f"  Num clients (K)         : {s['num_clients']}")
    print(f"  Rank-r compression      : {s['rank_r']}")
    print(f"  C matrix dominance      : {s['c_dominance_pct']:.1f}% of total per-client cost")
    print(f"{'-'*62}")
    print(f"  {'':32s} {'Original':>10}  {'Compressed':>10}")
    print(f"{'-'*62}")
    print(f"  {'W matrix  (per client)':32s} {s['W_orig_MB']:>9.4f}MB  {s['W_comp_MB']:>9.4f}MB")
    print(f"  {'C matrix  (per client)':32s} {s['C_MB']:>9.4f}MB  {s['C_MB']:>9.4f}MB")
    print(f"  {'Total     (per client)':32s} {s['orig_per_client_MB']:>9.4f}MB  {s['comp_per_client_MB']:>9.4f}MB")
    print(f"{'-'*62}")
    print(f"  {'TOTAL     (all clients)':32s} {s['orig_total_MB']:>9.3f}MB  {s['comp_total_MB']:>9.3f}MB")
    print(f"  {'W-only savings':32s} {s['w_saving_pct']:>9.1f}%")
    print(f"  {'Overall savings':32s} {s['saving_pct']:>9.1f}%  ({s['saving_MB']:.3f} MB saved)")
    if s['saving_pct'] < 1.0:
        print(f"\n  NOTE: Low saving because C matrix ({s['C_MB']:.3f} MB) dominates W.")
        print(f"        Use CIFAR-100/TinyImageNet for meaningful W compression gains.")
        print(f"        To show larger overall savings, compress C as well (future work).")
    print(f"{sep}\n")
