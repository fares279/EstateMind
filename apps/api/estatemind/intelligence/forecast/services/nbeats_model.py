"""
N-BEATS: Neural Basis Expansion Analysis Time Series.
A PyTorch-based neural forecasting model for univariate time series.

References:
  - Oreshkin et al. "N-BEATS: Neural basis expansion analysis for interpretable time series forecasting"
    https://arxiv.org/abs/1905.10437
"""

import logging
import warnings
from typing import Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import TensorDataset, DataLoader

logger = logging.getLogger(__name__)

# Suppress PyTorch warnings
warnings.filterwarnings("ignore", category=UserWarning)


class NBeatsStack(nn.Module):
    """
    Single stack (series-to-series block) in N-BEATS.
    Produces both backcast and forecast outputs.
    """

    def __init__(
        self, input_size: int, output_size: int, hidden_size: int = 64, n_layers: int = 2
    ):
        super().__init__()
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_size = hidden_size

        # Fully connected layers for feature extraction
        layers = []
        layers.append(nn.Linear(input_size, hidden_size))
        layers.append(nn.ReLU())
        for _ in range(n_layers - 1):
            layers.append(nn.Linear(hidden_size, hidden_size))
            layers.append(nn.ReLU())

        self.fc = nn.Sequential(*layers)

        # Output layers: backcast and forecast
        self.backcast = nn.Linear(hidden_size, input_size)
        self.forecast = nn.Linear(hidden_size, output_size)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: shape (batch_size, input_size)

        Returns:
            backcast: (batch_size, input_size)
            forecast: (batch_size, output_size)
        """
        hidden = self.fc(x)
        backcast = self.backcast(hidden)
        forecast = self.forecast(hidden)
        return backcast, forecast


class NBeatsNet(nn.Module):
    """
    N-BEATS network: stacks of residual blocks for time series forecasting.
    """

    def __init__(
        self,
        input_size: int,
        output_size: int,
        n_stacks: int = 2,
        hidden_size: int = 64,
        n_layers: int = 2,
    ):
        super().__init__()
        self.input_size = input_size
        self.output_size = output_size
        self.n_stacks = n_stacks

        self.stacks = nn.ModuleList(
            [
                NBeatsStack(input_size, output_size, hidden_size, n_layers)
                for _ in range(n_stacks)
            ]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: shape (batch_size, input_size)

        Returns:
            forecast: (batch_size, output_size)
        """
        residual = x
        forecast = torch.zeros(x.shape[0], self.output_size, device=x.device)

        for stack in self.stacks:
            backcast, stack_forecast = stack(residual)
            residual = residual - backcast
            forecast = forecast + stack_forecast

        return forecast


class NBeatsForecaster:
    """
    Wrapper for N-BEATS neural forecasting model.
    Handles training, prediction, and residual tracking.

    Args:
        input_size: Number of lookback steps (typically 12 for monthly data)
        output_size: Forecast horizon (typically 12 for monthly data)
        hidden_size: Hidden dimension for FC layers (default 64)
        n_stacks: Number of N-BEATS stacks (default 2)
        n_layers: Number of FC layers per stack (default 2)
        batch_size: Training batch size (default 8)
        epochs: Number of training epochs (default 100)
        learning_rate: Optimizer learning rate (default 0.001)
        device: PyTorch device ('cpu' or 'cuda', auto-detected if None)
    """

    def __init__(
        self,
        input_size: int = 12,
        output_size: int = 12,
        hidden_size: int = 64,
        n_stacks: int = 2,
        n_layers: int = 2,
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

        # Auto-detect device
        if device is None:
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(device)

        # Initialize model
        self.model = NBeatsNet(
            input_size=input_size,
            output_size=output_size,
            n_stacks=n_stacks,
            hidden_size=hidden_size,
            n_layers=n_layers,
        ).to(self.device)

        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.MSELoss()
        self.is_trained = False
        self.training_residuals = []

    def _create_sliding_windows(self, series: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """
        Create sliding windows for training.

        Args:
            series: 1D price array

        Returns:
            X: shape (n_windows, input_size)
            y: shape (n_windows, output_size)
        """
        X, y = [], []
        for i in range(len(series) - self.input_size - self.output_size + 1):
            X.append(series[i : i + self.input_size])
            y.append(series[i + self.input_size : i + self.input_size + self.output_size])
        return np.array(X), np.array(y)

    def fit(
        self,
        train_prices: np.ndarray,
        verbose: bool = False,
    ) -> dict:
        """
        Train the N-BEATS model on historical price data.

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
                f"Insufficient data for N-BEATS: {len(train_prices)} < "
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
        dataset = TensorDataset(
            torch.FloatTensor(X_norm), torch.FloatTensor(y_norm)
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
                y_pred = self.model(X_batch)
                loss = self.criterion(y_pred, y_batch)
                loss.backward()
                self.optimizer.step()

                epoch_loss += loss.item()

            if verbose and (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch + 1}/{self.epochs}, Loss: {epoch_loss:.6f}")

        # Compute training residuals for conformal calibration
        self.model.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_norm).to(self.device)
            y_pred_norm = self.model(X_tensor).cpu().numpy()

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
            logger.info(f"N-BEATS training complete. Final loss: {epoch_loss:.6f}")

        return {
            "status": "success",
            "loss": float(epoch_loss),
            "n_samples": n_samples,
        }

    def forecast(self, n_steps: int = 12) -> Tuple[np.ndarray, list]:
        """
        Generate forecast and residuals.

        Args:
            n_steps: Number of steps to forecast (default 12)

        Returns:
            tuple (forecast_array, residuals)
                - forecast_array: 1D array of length n_steps
                - residuals: List of training residuals for conformal calibration
        """
        if not self.is_trained:
            logger.warning("Model not trained. Cannot forecast.")
            return np.array([]), []

        # Use most recent input_size observations for forecast
        # (In production, this would be called after fit with latest data)
        self.model.eval()
        
        # Return zeros as placeholder - actual implementation would use latest data
        # This is populated by the backtester with the latest window
        forecast = np.zeros(n_steps)
        return forecast, self.training_residuals

    def predict_from_window(self, window: np.ndarray, n_steps: int = 12) -> np.ndarray:
        """
        Generate forecast from a specific input window.

        Args:
            window: 1D array of length input_size (the lookback window)
            n_steps: Number of steps to forecast (default 12)

        Returns:
            forecast: 1D array of length n_steps
        """
        if not self.is_trained:
            logger.warning("Model not trained. Cannot forecast.")
            return np.zeros(n_steps)

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
            window_tensor = torch.FloatTensor(window_norm).unsqueeze(0).to(self.device)

            # Predict
            forecast_norm = self.model(window_tensor).cpu().numpy()[0]

            # Denormalize
            forecast = forecast_norm * self.y_std + self.y_mean

        return forecast

    def get_residuals(self) -> list:
        """Get training residuals for conformal calibration."""
        return self.training_residuals
