"""
Temporal Fusion Transformer (TFT): A PyTorch-based multi-horizon forecaster.
Produces native quantile predictions without external wrapping.

References:
  - Lim et al. "Temporal Fusion Transformers for Interpretable Multi-horizon Time Series Forecasting"
    https://arxiv.org/abs/1912.09363
"""

import logging
import warnings
from typing import Tuple, List, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader

logger = logging.getLogger(__name__)

# Suppress PyTorch warnings
warnings.filterwarnings("ignore", category=UserWarning)


class MultiHeadAttention(nn.Module):
    """Simple multi-head attention for TFT backbone."""

    def __init__(self, hidden_size: int, n_heads: int = 4):
        super().__init__()
        self.hidden_size = hidden_size
        self.n_heads = n_heads
        self.head_dim = hidden_size // n_heads

        assert hidden_size % n_heads == 0, "hidden_size must be divisible by n_heads"

        self.query = nn.Linear(hidden_size, hidden_size)
        self.key = nn.Linear(hidden_size, hidden_size)
        self.value = nn.Linear(hidden_size, hidden_size)
        self.out = nn.Linear(hidden_size, hidden_size)

    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor,
                mask: Optional[torch.Tensor] = None) -> torch.Tensor:
        """
        Args:
            query, key, value: (batch_size, seq_len, hidden_size)
            mask: (batch_size, seq_len) optional

        Returns:
            output: (batch_size, seq_len, hidden_size)
        """
        batch_size = query.shape[0]

        # Linear transformations
        Q = self.query(query).view(batch_size, -1, self.n_heads, self.head_dim).transpose(1, 2)
        K = self.key(key).view(batch_size, -1, self.n_heads, self.head_dim).transpose(1, 2)
        V = self.value(value).view(batch_size, -1, self.n_heads, self.head_dim).transpose(1, 2)

        # Scaled dot-product attention
        scores = torch.matmul(Q, K.transpose(-2, -1)) / np.sqrt(self.head_dim)

        if mask is not None:
            scores = scores.masked_fill(mask.unsqueeze(1).unsqueeze(1) == 0, float('-inf'))

        attention = torch.softmax(scores, dim=-1)
        out = torch.matmul(attention, V)

        # Concatenate heads
        out = out.transpose(1, 2).contiguous().view(batch_size, -1, self.hidden_size)
        out = self.out(out)

        return out


class TFTEncoder(nn.Module):
    """Temporal Fusion Transformer encoder block."""

    def __init__(self, hidden_size: int = 64, n_heads: int = 4, dropout: float = 0.1):
        super().__init__()
        self.attention = MultiHeadAttention(hidden_size, n_heads)
        self.feed_forward = nn.Sequential(
            nn.Linear(hidden_size, hidden_size * 4),
            nn.ReLU(),
            nn.Linear(hidden_size * 4, hidden_size),
        )
        self.norm1 = nn.LayerNorm(hidden_size)
        self.norm2 = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch_size, seq_len, hidden_size)

        Returns:
            out: (batch_size, seq_len, hidden_size)
        """
        # Self-attention with residual
        attn_out = self.attention(x, x, x)
        x = self.norm1(x + self.dropout(attn_out))

        # Feed-forward with residual
        ff_out = self.feed_forward(x)
        x = self.norm2(x + self.dropout(ff_out))

        return x


class TFTNet(nn.Module):
    """Temporal Fusion Transformer network."""

    def __init__(
        self,
        input_size: int,
        output_size: int,
        hidden_size: int = 64,
        n_layers: int = 2,
        n_heads: int = 4,
        n_quantiles: int = 5,
    ):
        super().__init__()
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_size = hidden_size
        self.n_quantiles = n_quantiles

        # Input projection
        self.input_projection = nn.Linear(1, hidden_size)

        # Transformer encoder blocks
        self.encoder = nn.ModuleList([
            TFTEncoder(hidden_size, n_heads) for _ in range(n_layers)
        ])

        # Quantile output heads: produce n_quantiles per horizon step
        self.quantile_heads = nn.ModuleList([
            nn.Linear(hidden_size, n_quantiles) for _ in range(output_size)
        ])

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch_size, input_size, 1) - univariate time series

        Returns:
            quantiles: (batch_size, output_size, n_quantiles)
        """
        # Project input
        x = self.input_projection(x)  # (batch_size, input_size, hidden_size)

        # Encode with Transformer
        for encoder_layer in self.encoder:
            x = encoder_layer(x)

        # Take last hidden state and project to quantiles for each horizon
        x_last = x[:, -1, :]  # (batch_size, hidden_size)

        # Generate quantile predictions for each horizon
        quantiles = []
        for i, head in enumerate(self.quantile_heads):
            q = head(x_last)  # (batch_size, n_quantiles)
            quantiles.append(q)

        quantiles = torch.stack(quantiles, dim=1)  # (batch_size, output_size, n_quantiles)

        return quantiles


class TFTForecaster:
    """
    Wrapper for Temporal Fusion Transformer model.
    Produces native quantile predictions without external conformal wrapper.

    Args:
        input_size: Number of lookback steps (typically 24 for monthly data)
        output_size: Forecast horizon (typically 12 for monthly data)
        hidden_size: Hidden dimension for Transformer (default 64)
        n_layers: Number of Transformer encoder blocks (default 2)
        n_heads: Number of attention heads (default 4)
        n_quantiles: Number of quantile levels to predict (default 5)
        quantile_levels: Specific quantile levels (e.g., [0.1, 0.3, 0.5, 0.7, 0.9])
        batch_size: Training batch size (default 8)
        epochs: Number of training epochs (default 100)
        learning_rate: Optimizer learning rate (default 0.001)
        device: PyTorch device ('cpu' or 'cuda', auto-detected if None)
    """

    def __init__(
        self,
        input_size: int = 24,
        output_size: int = 12,
        hidden_size: int = 64,
        n_layers: int = 2,
        n_heads: int = 4,
        n_quantiles: int = 5,
        quantile_levels: Optional[List[float]] = None,
        batch_size: int = 8,
        epochs: int = 100,
        learning_rate: float = 0.001,
        device: str = None,
    ):
        self.input_size = input_size
        self.output_size = output_size
        self.batch_size = batch_size
        self.epochs = epochs
        self.learning_rate = learning_rate
        self.n_quantiles = n_quantiles

        # Quantile levels (default: deciles + median)
        if quantile_levels is None:
            self.quantile_levels = [0.1, 0.3, 0.5, 0.7, 0.9]
        else:
            self.quantile_levels = quantile_levels
            self.n_quantiles = len(quantile_levels)

        # Auto-detect device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        # Initialize model
        self.model = TFTNet(
            input_size=input_size,
            output_size=output_size,
            hidden_size=hidden_size,
            n_layers=n_layers,
            n_heads=n_heads,
            n_quantiles=self.n_quantiles,
        ).to(self.device)

        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.is_trained = False
        self.training_residuals = []

    def _create_sliding_windows(self, series: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Create sliding windows for training."""
        X, y = [], []
        for i in range(len(series) - self.input_size - self.output_size + 1):
            X.append(series[i : i + self.input_size])
            y.append(series[i + self.input_size : i + self.input_size + self.output_size])
        return np.array(X), np.array(y)

    def _quantile_loss(
        self, predictions: torch.Tensor, targets: torch.Tensor, quantiles: List[float]
    ) -> torch.Tensor:
        """
        Quantile loss (pinball loss) for multi-quantile regression.

        Args:
            predictions: (batch_size, output_size, n_quantiles)
            targets: (batch_size, output_size)
            quantiles: List of quantile levels

        Returns:
            loss: scalar
        """
        loss = 0.0
        for q_idx, q in enumerate(quantiles):
            errors = targets - predictions[:, :, q_idx]  # (batch_size, output_size)
            loss += torch.mean(torch.max(q * errors, (q - 1) * errors))

        return loss / len(quantiles)

    def fit(
        self,
        train_prices: np.ndarray,
        verbose: bool = False,
    ) -> dict:
        """
        Train the TFT model on historical price data.

        Args:
            train_prices: 1D array of historical prices (length >= input_size + output_size)
            verbose: If True, log training progress

        Returns:
            dict with keys:
                - 'loss': Final training loss
                - 'n_samples': Number of training windows
                - 'status': 'success' or 'insufficient_data'
        """
        # Check data availability
        if len(train_prices) < self.input_size + self.output_size:
            logger.warning(
                f"Insufficient data for TFT: {len(train_prices)} < "
                f"{self.input_size + self.output_size}. Skipping training."
            )
            self.is_trained = False
            return {"status": "insufficient_data", "loss": float("inf"), "n_samples": 0}

        # Create sliding windows
        X, y = self._create_sliding_windows(train_prices)
        n_samples = len(X)

        # Normalize
        X_mean, X_std = X.mean(), X.std() + 1e-8
        y_mean, y_std = y.mean(), y.std() + 1e-8

        X_norm = (X - X_mean) / X_std
        y_norm = (y - y_mean) / y_std

        # Create DataLoader
        # Reshape X to (batch_size, input_size, 1) for univariate input
        X_norm_reshaped = X_norm.reshape(X_norm.shape[0], X_norm.shape[1], 1)
        dataset = TensorDataset(
            torch.FloatTensor(X_norm_reshaped), torch.FloatTensor(y_norm)
        )
        dataloader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        # Train
        self.model.train()
        for epoch in range(self.epochs):
            epoch_loss = 0.0
            for X_batch, y_batch in dataloader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                self.optimizer.zero_grad()
                y_pred_quantiles = self.model(X_batch)  # (batch_size, output_size, n_quantiles)
                loss = self._quantile_loss(y_pred_quantiles, y_batch, self.quantile_levels)
                loss.backward()
                self.optimizer.step()

                epoch_loss += loss.item()

            if verbose and (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{self.epochs}, Loss: {epoch_loss:.6f}")

        # Compute training residuals using median quantile (0.5)
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_norm_reshaped).to(self.device)
            y_pred_quantiles_norm = self.model(X_tensor).cpu().numpy()

        # Extract median quantile (index 2 for [0.1, 0.3, 0.5, 0.7, 0.9])
        median_idx = self.quantile_levels.index(0.5)
        y_pred_norm = y_pred_quantiles_norm[:, :, median_idx]

        # Denormalize predictions
        y_pred = y_pred_norm * y_std + y_mean
        residuals = (y - y_pred).flatten().tolist()
        self.training_residuals = residuals

        # Store normalization params for inference
        self.X_mean = X_mean
        self.X_std = X_std
        self.y_mean = y_mean
        self.y_std = y_std

        self.is_trained = True

        if verbose:
            logger.info(f"TFT training complete. Final loss: {epoch_loss:.6f}")

        return {
            "status": "success",
            "loss": float(epoch_loss),
            "n_samples": n_samples,
        }

    def predict_from_window(self, window: np.ndarray, n_steps: int = 12) -> dict:
        """
        Generate quantile forecast from a specific input window.

        Args:
            window: 1D array of length input_size (the lookback window)
            n_steps: Number of steps to forecast (default 12)

        Returns:
            dict with:
                - 'point': Point forecast (median quantile)
                - 'quantiles': Dict of quantile level -> forecast array
                - 'lower': Lower bound (q0.1)
                - 'upper': Upper bound (q0.9)
        """
        if not self.is_trained:
            logger.warning("Model not trained. Cannot forecast.")
            return {}

        if len(window) != self.input_size:
            logger.warning(
                f"Window size {len(window)} != expected {self.input_size}. Padding/truncating."
            )
            if len(window) < self.input_size:
                window = np.concatenate(
                    [np.full(self.input_size - len(window), window[0]), window]
                )
            else:
                window = window[-self.input_size :]

        self.model.eval()
        with torch.no_grad():
            # Normalize
            window_norm = (window - self.X_mean) / self.X_std
            window_tensor = (
                torch.FloatTensor(window_norm).unsqueeze(0).unsqueeze(-1).to(self.device)
            )
            # (1, input_size, 1)

            # Predict quantiles
            quantiles_norm = self.model(window_tensor).cpu().numpy()[0]
            # (output_size, n_quantiles)

            # Denormalize
            quantiles_denorm = quantiles_norm * self.y_std + self.y_mean

        # Extract quantile levels
        result = {
            'quantiles': {}
        }

        for q_idx, q_level in enumerate(self.quantile_levels):
            result['quantiles'][q_level] = quantiles_denorm[:, q_idx].tolist()

        # Point forecast: use median quantile
        median_idx = self.quantile_levels.index(0.5)
        result['point'] = quantiles_denorm[:, median_idx].tolist()

        # Confidence bounds
        lower_idx = self.quantile_levels.index(0.1)
        upper_idx = self.quantile_levels.index(0.9)
        result['lower'] = quantiles_denorm[:, lower_idx].tolist()
        result['upper'] = quantiles_denorm[:, upper_idx].tolist()

        return result

    def get_residuals(self) -> list:
        """Get training residuals for backward compatibility with conformal."""
        return self.training_residuals
