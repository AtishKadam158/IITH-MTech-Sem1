import numpy as np


class Adaline:
    def __init__(self, learning_rate=1.0, max_iterations=1000):
        self.learning_rate = float(learning_rate)
        self.max_iterations = int(max_iterations)
        self.weights_ = None   # set after fit(); shape (n_features,)
        self.bias_ = 0.0
        self.mse_train_ = []   # MSE per epoch — training set
        self.mse_val_ = None   # MSE per epoch — validation set (optional)

    def _init_weights(self, n_features, seed=42):
        # small random weights to break symmetry; bias starts at zero
        rng = np.random.default_rng(seed)
        self.weights_ = rng.normal(0.0, 0.01, size=(n_features,))
        self.bias_ = 0.0

    def _linear_output(self, X):
        # net input: X @ w + b  (no activation — ADALINE uses raw linear output)
        return X @ self.weights_ + self.bias_

    def fit(self, X, y, X_val=None, y_val=None, verbose=False):
        X = np.array(X, dtype=float)
        y = np.array(y, dtype=float).ravel()
        n_samples, n_features = X.shape

        self._init_weights(n_features)
        self.mse_train_ = []
        self.mse_val_ = [] if (X_val is not None and y_val is not None) else None

        log_at = max(1, self.max_iterations // 10)

        for epoch in range(self.max_iterations):
            errors = y - self._linear_output(X)   # residuals (y - ŷ)

            # record MSE before the weight update
            train_mse = float(np.mean(errors ** 2))
            self.mse_train_.append(train_mse)

            # stop early if weights have diverged (nan / inf)
            if not np.isfinite(train_mse):
                if verbose:
                    print(f"  Epoch {epoch+1:>4}: diverged — stopping early.")
                break

            if self.mse_val_ is not None:
                Xv, yv = np.array(X_val, dtype=float), np.array(y_val, dtype=float).ravel()
                self.mse_val_.append(float(np.mean((yv - self._linear_output(Xv)) ** 2)))

            # batch gradient descent (Widrow-Hoff / LMS rule)
            # ∇w = -(2/n) X^T e  →  w += lr * X^T e / n
            self.weights_ += self.learning_rate * (X.T @ errors) / n_samples
            self.bias_    += self.learning_rate * float(np.mean(errors))

            if verbose and ((epoch + 1) % log_at == 0 or epoch == 0):
                msg = f"  Epoch {epoch+1:>4}/{self.max_iterations}  train_mse={train_mse:.5f}"
                if self.mse_val_:
                    msg += f"  val_mse={self.mse_val_[-1]:.5f}"
                print(msg)

        return self.mse_train_

    def predict(self, X):
        if self.weights_ is None:
            raise RuntimeError("Model has not been trained. Call fit() first.")
        return self._linear_output(np.array(X, dtype=float))

    def score(self, X, y):
        # returns MSE (lower is better)
        y_pred = self.predict(X).ravel()
        y_true = np.array(y, dtype=float).ravel()
        return float(np.mean((y_true - y_pred) ** 2))