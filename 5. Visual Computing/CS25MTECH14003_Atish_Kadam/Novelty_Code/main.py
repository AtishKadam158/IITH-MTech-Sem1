import argparse
import os
import random
import time
import warnings
import csv

import torch
import torch.backends.cudnn as cudnn
import torch.utils.data
import torchvision.models
import numpy as np
from torch.utils.data import Subset

from dataset import prepare_data
from afl import (LinearAnalytic, init_local, local_update, aggregation,
                 clean_regularization, validate,
                 compute_comm_cost, print_comm_cost_report)

# ARGUMENTS

parser = argparse.ArgumentParser(description='AFL Training')

parser.add_argument('--dataset',    default='cifar100', type=str,
                    choices=['cifar10', 'cifar100', 'tinyimagenet'])
parser.add_argument('-a', '--arch', default='resnet18')
parser.add_argument('--batch-size', default=512, type=int)
parser.add_argument('--pretrained', action='store_true')
parser.add_argument('--gpu',        default=0, type=int)

# Data
parser.add_argument('--data',    default='./data',    type=str)
parser.add_argument('--datadir', default='./dataset', type=str)

# Seeds
parser.add_argument('--seed',      default=1, type=int)
parser.add_argument('--modelseed', default=1, type=int)

# Federated Learning
parser.add_argument('--num_clients', default=50,    type=int)
# NOTE: --num_classes is auto-set from --dataset below; override only if needed.
parser.add_argument('--num_classes', default=None,  type=int)
parser.add_argument('--niid',        action='store_true')
parser.add_argument('--balance',     action='store_true')
parser.add_argument('--partition',   default='dir', type=str)
parser.add_argument('--alpha',       default=0.1,   type=float)
parser.add_argument('--shred',       default=10,    type=int)

# Regularisation
parser.add_argument('--rg',        default=0,    type=float,
                    help='Ridge regularisation coefficient. '
                         'Set > 0 (e.g. 1.0) for stable inversion. '
                         'When 0, an automatic data-driven value is used.')
parser.add_argument('--clean_reg', action='store_true',
                    help='Remove regularisation bias after aggregation '
                         '(requires --rg > 0).')

# Rank-r compression (contribution)
parser.add_argument('--rank_r', default=0, type=int,
                    help='Rank-r SVD compression applied to each client\'s '
                         'local weight matrix before aggregation (0 = disabled).')


# =============================================================================
# MAIN
# =============================================================================
def main():
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Auto-set num_classes from dataset name so the user does not have to
    # pass --num_classes explicitly (and cannot silently pass the wrong value).
    # -------------------------------------------------------------------------
    dataset_classes = {'cifar10': 10, 'cifar100': 100, 'tinyimagenet': 200}
    if args.num_classes is None:
        args.num_classes = dataset_classes.get(args.dataset, 100)
    print(f"Dataset: {args.dataset}  |  num_classes: {args.num_classes}")

    # -------------------------------------------------------------------------
    # Warn when rg=0 (auto-regularisation will kick in inside local_update)
    # -------------------------------------------------------------------------
    if args.rg == 0:
        warnings.warn(
            "--rg is 0: auto-regularisation will be used per client. "
            "For reproducible results pass an explicit value, e.g. --rg 1."
        )
    if args.clean_reg and args.rg == 0:
        warnings.warn(
            "--clean_reg has no effect when --rg 0 because there is no "
            "explicit regularisation to remove."
        )

    # -------------------------------------------------------------------------
    # Seeds
    # -------------------------------------------------------------------------
    random.seed(args.modelseed)
    torch.manual_seed(args.modelseed)
    np.random.seed(args.seed)
    cudnn.deterministic = True
    cudnn.benchmark     = False
    warnings.warn("Deterministic mode enabled")

    print(f"Using GPU: {args.gpu}")

    # -------------------------------------------------------------------------
    # Backbone
    # -------------------------------------------------------------------------
    import resnet as resnet_module

    if args.pretrained:
        print(f"=> using pre-trained model '{args.arch}'")
        model_pretrain = torchvision.models.__dict__[args.arch](
            weights=torchvision.models.ResNet18_Weights.IMAGENET1K_V1
            if args.arch == 'resnet18' else None
        )
        model = resnet_module.__dict__[args.arch](args.num_classes)
        model.load_state_dict(model_pretrain.state_dict(), strict=False)
        args.feat_size = model_pretrain.fc.weight.size(1)
    else:
        print(f"=> creating model '{args.arch}'")
        model = resnet_module.__dict__[args.arch](args.num_classes)
        args.feat_size = 512

    model = model.cuda(args.gpu)
    model.eval()

    # -------------------------------------------------------------------------
    # Data
    # -------------------------------------------------------------------------
    train_total, train_data_idx, testset = prepare_data(args)

    train_dataset = [Subset(train_total, train_data_idx[idx])
                     for idx in range(args.num_clients)]

    # -------------------------------------------------------------------------
    # Global analytic head (identity projection, weights set after aggregation)
    # -------------------------------------------------------------------------
    global_model = LinearAnalytic(args.feat_size, args.num_classes).cuda(args.gpu)

    local_weights, local_R, local_C = [], [], []
    local_train_acc = []

    # =========================================================================
    # LOCAL TRAINING
    # =========================================================================
    print("\nTraining locally!")
    start = time.time()

    for idx in range(args.num_clients):
        train_loader = torch.utils.data.DataLoader(
            train_dataset[idx],
            batch_size=args.batch_size,
            shuffle=True,
            num_workers=2,
            pin_memory=True,
        )

        W, R, C = local_update(train_loader, model, global_model, args)

        # Evaluate local model accuracy
        local_model = init_local(args)
        local_model.fc.weight = torch.nn.Parameter(torch.t(W.float()))
        correct, num_sample = validate(train_loader, model, local_model.cuda(), args)
        acc = (correct / num_sample).item()

        print(f"Client {idx} Train Acc: {acc * 100:.2f}%")

        local_weights.append(W.cpu())
        local_R.append(R)
        local_C.append(C)
        local_train_acc.append(acc)

    endtime = time.time() - start
    print(f"Local training time: {endtime:.2f}s")

    # =========================================================================
    # AGGREGATION
    # =========================================================================
    print("\nAggregating!")
    global_weight, global_R, global_C = aggregation(local_weights, local_R, local_C, args)
    print("Aggregation done!")

    # =========================================================================
    # COMMUNICATION COST REPORT
    # =========================================================================
    comm_stats = compute_comm_cost(
        feat_size   = args.feat_size,
        num_classes = args.num_classes,
        num_clients = args.num_clients,
        rank_r      = args.rank_r,
    )
    print_comm_cost_report(comm_stats)

    global_model.fc.weight = torch.nn.Parameter(torch.t(global_weight.float()))

    # =========================================================================
    # EVALUATION  (before optional cleaning)
    # =========================================================================
    print("\nEvaluating global model!")
    val_loader = torch.utils.data.DataLoader(
        testset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=True,
    )

    correct, num_sample = validate(val_loader, model, global_model, args)
    acc = (correct / num_sample * 100).item()

    endtime_1 = time.time() - start
    print(f"Total time (train + agg): {endtime_1:.2f}s")
    print(f"Global Accuracy: {acc:.2f}%")

    # =========================================================================
    # CLEAN REGULARIZATION  (optional)
    # =========================================================================
    acc_c = None

    if args.clean_reg and args.rg > 0:
        print("\nCleaning regularization...")
        global_weight_clean = clean_regularization(global_weight, global_C, args)
        global_model.fc.weight = torch.nn.Parameter(torch.t(global_weight_clean.float()))

        correct_c, num_sample = validate(val_loader, model, global_model, args)
        acc_c = (correct_c / num_sample * 100).item()
        print(f"Accuracy after cleaning: {acc_c:.2f}%")

    endtime_2 = time.time() - start
    print(f"Total time (with cleaning): {endtime_2:.2f}s")

    # =========================================================================
    # CSV LOGGING
    # =========================================================================
    filename = f"{args.dataset}_{args.arch}_{args.num_clients}_{args.alpha}.csv"
    with open(filename, mode='a+', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([
            str(local_train_acc),
            '-',
            f"{acc:.4f}",
            f"{acc_c:.4f}" if acc_c is not None else "NA",
            '-',
            f"{endtime:.2f}",
            f"{endtime_1:.2f}",
            f"{endtime_2:.2f}",
            '-',
            f"orig_total_MB={comm_stats['orig_total_MB']:.3f}",
            f"comp_total_MB={comm_stats['comp_total_MB']:.3f}",
            f"saving_MB={comm_stats['saving_MB']:.3f}",
            f"saving_pct={comm_stats['saving_pct']:.1f}",
            f"rank_r={comm_stats['rank_r']}",
            '-',
            str(args),
        ])

    print(f"Saved results to {filename}")


# =============================================================================
# ENTRY POINT
# =============================================================================
if __name__ == '__main__':
    main()