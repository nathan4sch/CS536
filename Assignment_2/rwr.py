import json
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from torch.utils.data import Dataset, DataLoader

# ==============================
# Hyperparameters
# ==============================

ALPHA = 1e6   # scale RTT penalty
BETA = 1e5     # scale loss penalty
TAU = 1.0      # reward temperature
LR = 5e-2
EPOCHS = 100
BATCH_SIZE = 128
TRAIN_SPLIT = 0.8
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(DEVICE)

# ==============================
# Dataset Construction
# ==============================

class RWRDataset(Dataset):
    def __init__(self, states, actions, rewards):
        self.states = torch.tensor(states, dtype=torch.float32)
        self.actions = torch.tensor(actions, dtype=torch.float32).unsqueeze(1)
        self.rewards = torch.tensor(rewards, dtype=torch.float32)

        # normalize reward weights
        r = (self.rewards - self.rewards.mean()) / (self.rewards.std() + 1e-8)
        self.weights = torch.exp(r / TAU)

    def __len__(self):
        return len(self.states)

    def __getitem__(self, idx):
        return self.states[idx], self.actions[idx], self.weights[idx]

# ==============================
# MLP Policy Network
# ==============================

class PolicyNet(nn.Module):
    def __init__(self, input_dim):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, 1)
        )

    def forward(self, x):
        return self.net(x)

# ==============================
# Data Processing
# ==============================

def build_dataset(trace, alpha=ALPHA, beta=BETA):
    states, actions, rewards, cwnds = [], [], [], []

    for t in range(len(trace) - 1):
        s = trace[t]
        s_next = trace[t + 1]

        goodput = s["goodput_bps"]
        rtt = s["rtt_ms"]
        loss = s["total_retrans"]
        cwnd = s["snd_cwnd"]

        cwnd_next = s_next["snd_cwnd"]
        delta_cwnd = cwnd_next - cwnd

        reward = (
            s_next["goodput_bps"]
            - alpha * s_next["rtt_ms"]
            - beta * s_next["total_retrans"]
        )

        states.append([goodput, rtt, loss, cwnd])
        actions.append(delta_cwnd)
        rewards.append(reward)
        cwnds.append(cwnd)

    return np.array(states), np.array(actions), np.array(rewards), np.array(cwnds)

# ==============================
# Training Function
# ==============================

def train_rwr(policy, train_loader):
    optimizer = optim.Adam(policy.parameters(), lr=LR)

    for epoch in range(EPOCHS):
        total_loss = 0

        for states, actions, weights in train_loader:
            states = states.to(DEVICE)
            actions = actions.to(DEVICE)
            weights = weights.to(DEVICE)

            pred = policy(states)
            loss = (weights.unsqueeze(1) * (pred - actions) ** 2).mean()

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        print(f"Epoch {epoch+1}: Loss {total_loss:.4f}")

# ==============================
# Rollout on Test Split
# ==============================

def rollout(policy, states, cwnd_init, scaler):
    policy.eval()
    predicted_cwnd = []
    cwnd = cwnd_init

    with torch.no_grad():
        for s in states:
            s_mod = s.copy()
            s_mod[3] = cwnd  # replace cwnd with updated value
            s_norm = scaler.transform([s_mod])
            s_tensor = torch.tensor(s_norm, dtype=torch.float32).to(DEVICE)

            delta = policy(s_tensor).cpu().item()
            cwnd = cwnd + delta
            predicted_cwnd.append(cwnd)

    return predicted_cwnd

# ==============================
# Main Pipeline
# ==============================

def run_trace(trace, destination_name):
    states, actions, rewards, cwnds = build_dataset(trace)

    split = int(len(states) * TRAIN_SPLIT)

    scaler = StandardScaler()
    scaler.fit(states[:split])

    states_norm = scaler.transform(states)

    train_dataset = RWRDataset(
        states_norm[:split],
        actions[:split],
        rewards[:split]
    )

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)

    policy = PolicyNet(input_dim=4).to(DEVICE)
    train_rwr(policy, train_loader)

    # Rollout on test portion
    predicted_cwnd = rollout(
        policy,
        states[split:],
        cwnd_init=cwnds[split],
        scaler=scaler
    )

    true_cwnd = cwnds
    test_indices = range(split, split + len(predicted_cwnd))

    plt.figure(figsize=(10,5))
    plt.plot(true_cwnd, label="True CWND")
    plt.plot(test_indices, predicted_cwnd, label="Predicted CWND (RWR)")
    plt.axvline(split, color="red", linestyle="--", label="Train/Test Split")
    plt.title(f"Destination {destination_name}")
    plt.legend()
    plt.savefig("test.png")

# ==============================
# Load JSON and Run
# ==============================

if __name__ == "__main__":
    with open("tcp_metrics.json", "r") as f:
        data = json.load(f)

    for dest, trace in list(data.items())[:5]:  # first 5 destinations
        print(f"Running for destination {dest}")
        run_trace(trace, dest)


# early stopping, validation set