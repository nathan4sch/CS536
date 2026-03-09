import json
import os
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

ALPHA = 1e6
BETA = 1e5
TAU = 5
LR = 5e-4
EPOCHS = 100
BATCH_SIZE = 64

TRAIN_RATIO = 0.7
VAL_RATIO = 0.1

PATIENCE = 10

HISTORY = 5

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(DEVICE)

os.makedirs("part3", exist_ok=True)

# ==============================
# Dataset
# ==============================

class RWRDataset(Dataset):

    def __init__(self, states, actions, rewards):

        self.states = torch.tensor(states, dtype=torch.float32)
        self.actions = torch.tensor(actions, dtype=torch.float32).unsqueeze(1)
        self.rewards = torch.tensor(rewards, dtype=torch.float32)

        r = (self.rewards - self.rewards.mean()) / (self.rewards.std() + 1e-8)
        self.weights = torch.exp(r / TAU)

        print("Weight stats:")
        print("min:", self.weights.min().item())
        print("max:", self.weights.max().item())
        print("mean:", self.weights.mean().item())

    def __len__(self):
        return len(self.states)

    def __getitem__(self, idx):
        return self.states[idx], self.actions[idx], self.weights[idx]


# ==============================
# Policy Network
# ==============================

class PolicyNet(nn.Module):

    def __init__(self, input_dim):

        super().__init__()

        self.net = nn.Linear(input_dim,1)

    def forward(self,x):
        return self.net(x)


# ==============================
# Build Dataset WITH HISTORY
# ==============================

def build_dataset(trace):

    states, actions, rewards, cwnds = [], [], [], []

    for t in range(HISTORY, len(trace)-1):

        history = []

        for h in range(HISTORY):

            s = trace[t-HISTORY+h]

            history.extend([
                s["goodput_bps"],
                s["rtt_ms"],
                s["total_retrans"],
                s["snd_cwnd"]
            ])

        s = trace[t]
        s_next = trace[t+1]

        cwnd = s["snd_cwnd"]
        cwnd_next = s_next["snd_cwnd"]

        delta_cwnd = cwnd_next - cwnd

        reward = (
            s_next["goodput_bps"]
            - ALPHA * s_next["rtt_ms"]
            - BETA * s_next["total_retrans"]
        )

        states.append(history)
        actions.append(delta_cwnd)
        rewards.append(reward)
        cwnds.append(cwnd)

    return (
        np.array(states),
        np.array(actions),
        np.array(rewards),
        np.array(cwnds)
    )


# ==============================
# Training
# ==============================

def train_rwr(policy,train_loader,val_loader):

    optimizer = optim.Adam(policy.parameters(),lr=LR)

    best_loss = float("inf")
    patience_counter = 0

    for epoch in range(EPOCHS):

        policy.train()
        train_loss = 0

        for states,actions,weights in train_loader:

            states = states.to(DEVICE)
            actions = actions.to(DEVICE)
            weights = weights.to(DEVICE)

            pred = policy(states)

            loss = (weights.unsqueeze(1)*(pred-actions)**2).mean()

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            train_loss += loss.item()

        policy.eval()
        val_loss = 0

        with torch.no_grad():

            for states,actions,weights in val_loader:

                states = states.to(DEVICE)
                actions = actions.to(DEVICE)
                weights = weights.to(DEVICE)

                pred = policy(states)

                loss = (weights.unsqueeze(1)*(pred-actions)**2).mean() # this is rlly the key line

                val_loss += loss.item()

        print(f"Epoch {epoch+1} Train:{train_loss:.4f} Val:{val_loss:.4f}")

        if val_loss < best_loss:

            best_loss = val_loss
            patience_counter = 0
            best_model = policy.state_dict()

        else:

            patience_counter += 1

        if patience_counter >= PATIENCE:

            print("Early stopping triggered")
            break

    policy.load_state_dict(best_model)


# ==============================
# Prediction (NO ROLLOUT)
# ==============================

def predict(policy,states,scaler):

    states_norm = scaler.transform(states)

    states_tensor = torch.tensor(states_norm,dtype=torch.float32).to(DEVICE)

    policy.eval()

    with torch.no_grad():

        delta = policy(states_tensor).cpu().numpy().flatten()

    return delta


# ==============================
# Plot Destination
# ==============================

def plot_destination(trace, policy, state_scaler, action_scaler, destination_name):
    states, actions, rewards, cwnds = build_dataset(trace)
    if len(states) == 0:
        return

    n = len(states)
    val_split = int((TRAIN_RATIO + VAL_RATIO) * n)

    # 1. Scale states and predict Delta CWND
    states_norm = state_scaler.transform(states)
    states_tensor = torch.tensor(states_norm, dtype=torch.float32).to(DEVICE)
    policy.eval()
    with torch.no_grad():
        pred_delta_norm = policy(states_tensor).cpu().numpy()
    
    # Inverse transform to get actual Delta cwnd
    pred_delta = action_scaler.inverse_transform(pred_delta_norm).flatten()

    # 2. Calculate 1-step prediction (CWND_t + Delta_pred)
    # This shows how the model performs given the ground truth state at every step
    pred_cwnd_1step = cwnds + pred_delta

    # 3. Calculate Cumulative Rollout (starting from the Val/Test split)
    # This shows the open-loop trajectory of your policy
    pred_cwnd_rollout = np.copy(cwnds)
    c = cwnds[val_split - 1] if val_split > 0 else cwnds[0]
    
    for i in range(val_split, n):
        c = c + pred_delta[i]
        pred_cwnd_rollout[i] = c

    # 4. Create vertically stacked plots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # Top Plot: 1-Step Prediction (Train, Val, and Test)
    ax1.plot(cwnds, label="True CWND", color="tab:blue", alpha=0.8)
    ax1.plot(pred_cwnd_1step, label="1-Step Predicted CWND", color="tab:orange", linestyle="--", alpha=0.7)
    ax1.axvline(val_split, color="red", linestyle="-.", label="Test Split Start")
    ax1.set_ylabel("CWND Size")
    ax1.set_title(f"Destination: {destination_name} - 1-Step Prediction")
    ax1.legend()

    # Bottom Plot: Cumulative Rollout (Focusing on the Test Split)
    test_idx = np.arange(val_split, n)
    ax2.plot(test_idx, cwnds[val_split:], label="True CWND", color="tab:blue")
    ax2.plot(test_idx, pred_cwnd_rollout[val_split:], label="Cumulative Rollout", color="tab:green", linewidth=2)
    ax2.set_ylabel("CWND Size")
    ax2.set_xlabel("Time Step")
    ax2.set_title("Test Horizon: Cumulative Policy Rollout")
    ax2.legend()

    plt.tight_layout()
    plt.savefig(f"part3/{destination_name}_combined.png")
    plt.close()

# ==============================
# Main
# ==============================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train RWR model")
    parser.add_argument("-f", "--file",
                        default="tcp_metrics_train.json",
                        help="Path to training JSON file")
    args = parser.parse_args()

    with open(args.file, "r") as f:
        data = json.load(f)

    train_states, train_actions, train_rewards = [], [], []
    val_states, val_actions, val_rewards = [], [], []

    destination_traces = list(data.items())

    for dest, trace in destination_traces:
        states, actions, rewards, _ = build_dataset(trace)
        if len(states) == 0:
            continue

        n = len(states)
        train_split = int(TRAIN_RATIO * n)
        val_split = int((TRAIN_RATIO + VAL_RATIO) * n)

        # Split PER TRACE to prevent data leakage across destinations
        train_states.append(states[:train_split])
        train_actions.append(actions[:train_split])
        train_rewards.append(rewards[:train_split])

        val_states.append(states[train_split:val_split])
        val_actions.append(actions[train_split:val_split])
        val_rewards.append(rewards[train_split:val_split])

    # Vertically stack the arrays
    train_states = np.vstack(train_states)
    train_actions = np.concatenate(train_actions).reshape(-1, 1) # Reshape for scaler
    train_rewards = np.concatenate(train_rewards)

    val_states = np.vstack(val_states)
    val_actions = np.concatenate(val_actions).reshape(-1, 1)
    val_rewards = np.concatenate(val_rewards)

    # Scale States
    state_scaler = StandardScaler()
    train_states_norm = state_scaler.fit_transform(train_states)
    val_states_norm = state_scaler.transform(val_states)

    # Scale Actions
    action_scaler = StandardScaler()
    train_actions_norm = action_scaler.fit_transform(train_actions).flatten()
    val_actions_norm = action_scaler.transform(val_actions).flatten()

    # Initialize Datasets
    train_dataset = RWRDataset(train_states_norm, train_actions_norm, train_rewards)
    val_dataset = RWRDataset(val_states_norm, val_actions_norm, val_rewards)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

    policy = PolicyNet(input_dim=4 * HISTORY).to(DEVICE)
    train_rwr(policy, train_loader, val_loader)

    print("Generating plots...")
    for i, (dest, trace) in enumerate(destination_traces):
        plot_destination(trace, policy, state_scaler, action_scaler, dest)