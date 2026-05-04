import numpy as np

def linear_kernel(xi, xj):
    return np.dot(xi, xj)


def polynomial_kernel(xi, xj, c=1.0, d=2):
    return np.power(np.dot(xi, xj) + c, d)


def rbf_kernel(xi, xj, gamma=0.1):
    diff = xi - xj
    sq_dist = np.dot(diff, diff)
    return np.exp(-gamma * sq_dist)


def neural_kernel(xi, xj, feature_extractor):
    
    phi_i = feature_extractor(xi)
    phi_j = feature_extractor(xj)
    return np.dot(phi_i, phi_j)




def compute_kernel_matrix(X, kernel_fn):
    
    n = X.shape[0]
    K = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            val = kernel_fn(X[i], X[j])
            K[i, j] = val
            K[j, i] = val
    return K


def compute_kernel_matrix_fast(X, kernel_fn):
   
    n = X.shape[0]
    K = np.zeros((n, n))
    for i in range(n):
        for j in range(i, n):
            v = kernel_fn(X[i], X[j])
            K[i, j] = v
            K[j, i] = v
    return K


def rbf_kernel_matrix(X, gamma=0.1):
    
    # ||xi - xj||^2 = ||xi||^2 + ||xj||^2 - 2 xi^T xj
    sq_norms = np.sum(X ** 2, axis=1)
    sq_dist = sq_norms[:, None] + sq_norms[None, :] - 2.0 * X.dot(X.T)
    sq_dist = np.maximum(sq_dist, 0.0)   # numerical safety
    return np.exp(-gamma * sq_dist)


def linear_kernel_matrix(X):
    return X.dot(X.T)


def poly_kernel_matrix(X, c=1.0, d=2):
    return np.power(X.dot(X.T) + c, d)


def neural_kernel_matrix(X, feature_extractor):
    """Efficient neural kernel matrix: Phi Phi^T"""
    Phi = np.array([feature_extractor(X[i]) for i in range(X.shape[0])])
    return Phi.dot(Phi.T)



class KernelSVR:

    def __init__(self, kernel_fn, C=1.0, epsilon=0.1, max_iter=1000, tol=1e-4, lr=0.01):
        self.kernel_fn = kernel_fn
        self.C = C
        self.epsilon = epsilon
        self.max_iter = max_iter
        self.tol = tol
        self.lr = lr   # gradient-ascent step for dual
        self.alphas = None   # alpha - alpha*
        self.b = 0.0
        self.X_train = None
        self.y_train = None

    
    # Fit using projected gradient ascent on the dual
    
    def fit(self, X, y):
        self.X_train = X.copy()
        self.y_train = y.copy()
        n = X.shape[0]

        # Pre-compute kernel matrix
        print("  [KernelSVR] Computing kernel matrix ...")
        K = np.zeros((n, n))
        for i in range(n):
            for j in range(i, n):
                v = self.kernel_fn(X[i], X[j])
                K[i, j] = v
                K[j, i] = v

        # Normalise kernel matrix: divide by mean diagonal value
        # This ensures the kernel values are on a common scale and prevents
        # divergence regardless of kernel type (linear, poly, RBF, neural)
        diag_mean = np.mean(np.diag(K)) + 1e-8
        K_n = K / diag_mean

        # Dual variables: beta = alpha - alpha*  in [-C, C]
        beta = np.zeros(n)
        b = 0.0

        eps = self.epsilon
        C = self.C

        # Compute a stable learning rate using Gershgorin bound on K_n
        row_sums = np.sum(np.abs(K_n), axis=1)
        safe_lr = 0.5 / (np.max(row_sums) + 1e-8)
        lr = min(self.lr, safe_lr)

        for iteration in range(self.max_iter):
            # Predictions on normalised kernel
            f = K_n.dot(beta) + b

            # Residuals
            res = y - f

            # Sub-gradient of epsilon-insensitive loss w.r.t. beta:
            # d/d_beta_i = sign(res_i) if |res_i| > eps, else 0
            grad = np.where(res > eps,  1.0,
                   np.where(res < -eps, -1.0, 0.0))

            # Update bias
            b_new = b + lr * np.mean(grad)

            # Update beta with projected gradient ascent
            beta_new = np.clip(beta + lr * grad, -C, C)

            # Convergence check
            delta = np.max(np.abs(beta_new - beta))
            beta = beta_new
            b = b_new

            if delta < self.tol:
                print(f"  [KernelSVR] Converged at iteration {iteration+1}")
                break

        # Scale alphas back from normalised kernel space
        self.alphas = beta / diag_mean
        self.b = b
        print(f"  [KernelSVR] Training done. "
              f"Non-zero SVs: {np.sum(np.abs(self.alphas) > 1e-8)}")

    def predict(self, X_test):
        n_test = X_test.shape[0]
        preds = np.zeros(n_test)
        for i in range(n_test):
            k_vec = np.array([self.kernel_fn(self.X_train[j], X_test[i])
                              for j in range(self.X_train.shape[0])])
            preds[i] = np.dot(self.alphas, k_vec) + self.b
        return preds

    def score(self, X_test, y_test):
        """R^2 score"""
        y_pred = self.predict(X_test)
        ss_res = np.sum(np.power(y_test - y_pred, 2))
        ss_tot = np.sum(np.power(y_test - np.mean(y_test), 2))
        return 1.0 - ss_res / (ss_tot + 1e-12)

    def mse(self, X_test, y_test):
        y_pred = self.predict(X_test)
        return np.mean(np.power(y_test - y_pred, 2))

    def rmse(self, X_test, y_test):
        return np.sqrt(self.mse(X_test, y_test))


def relu(z):
    return np.maximum(0.0, z)

def relu_grad(z):
    return (z > 0).astype(float)

def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -500, 500)))


class MLP:

    def __init__(self, layer_sizes, lr=0.001, epochs=200, batch_size=64, verbose=True):
        
        self.layer_sizes = layer_sizes
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.verbose = verbose
        self.weights = []
        self.biases = []
        self._init_params()

    def _init_params(self):
        self.weights = []
        self.biases = []
        for i in range(len(self.layer_sizes) - 1):
            fan_in = self.layer_sizes[i]
            fan_out = self.layer_sizes[i + 1]
            # He initialization
            std = np.sqrt(2.0 / fan_in)
            W = np.random.randn(fan_in, fan_out) * std
            b = np.zeros(fan_out)
            self.weights.append(W)
            self.biases.append(b)

    def _forward(self, X):
        """Returns list of pre/post activations for all layers."""
        activations = [X]
        pre_activations = []
        h = X
        for l in range(len(self.weights) - 1):
            z = h.dot(self.weights[l]) + self.biases[l]
            pre_activations.append(z)
            h = relu(z)
            activations.append(h)
        # Output layer: linear
        z_out = h.dot(self.weights[-1]) + self.biases[-1]
        pre_activations.append(z_out)
        activations.append(z_out)   # linear output
        return activations, pre_activations

    def predict(self, X):
        acts, _ = self._forward(X)
        return acts[-1].ravel()

    def penultimate_features(self, X):
        """Returns phi_NN(X): output of the last hidden layer."""
        acts, _ = self._forward(X)
        return acts[-2]   # before the output layer

    def _backprop(self, X, y):
        n = X.shape[0]
        acts, pre_acts = self._forward(X)
        y = y.reshape(-1, 1)

        # MSE loss
        delta = (acts[-1] - y) / n   # (n, 1)

        grads_W = []
        grads_b = []

        # Output layer (linear)
        gW = acts[-2].T.dot(delta)
        gb = np.sum(delta, axis=0)
        grads_W.insert(0, gW)
        grads_b.insert(0, gb)

        # Hidden layers (backprop through ReLU)
        delta_h = delta.dot(self.weights[-1].T)
        for l in range(len(self.weights) - 2, -1, -1):
            delta_h = delta_h * relu_grad(pre_acts[l])
            gW = acts[l].T.dot(delta_h)
            gb = np.sum(delta_h, axis=0)
            grads_W.insert(0, gW)
            grads_b.insert(0, gb)
            if l > 0:
                delta_h = delta_h.dot(self.weights[l].T)

        return grads_W, grads_b

    def fit(self, X, y):
        n = X.shape[0]
        loss_history = []
        for epoch in range(self.epochs):
            idx = np.random.permutation(n)
            X_shuf = X[idx]
            y_shuf = y[idx]

            for start in range(0, n, self.batch_size):
                Xb = X_shuf[start:start + self.batch_size]
                yb = y_shuf[start:start + self.batch_size]
                gW, gb = self._backprop(Xb, yb)
                for l in range(len(self.weights)):
                    self.weights[l] -= self.lr * gW[l]
                    self.biases[l] -= self.lr * gb[l]

            # Compute epoch loss
            y_pred = self.predict(X)
            loss = np.mean(np.power(y - y_pred, 2))
            loss_history.append(loss)
            if self.verbose and (epoch + 1) % 50 == 0:
                print(f"  Epoch [{epoch+1}/{self.epochs}]  MSE Loss: {loss:.4f}")
        return loss_history

    def score(self, X, y):
        y_pred = self.predict(X)
        ss_res = np.sum(np.power(y - y_pred, 2))
        ss_tot = np.sum(np.power(y - np.mean(y), 2))
        return 1.0 - ss_res / (ss_tot + 1e-12)

    def rmse(self, X, y):
        return np.sqrt(np.mean(np.power(y - self.predict(X), 2)))