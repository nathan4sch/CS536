import gurobipy as gp
from gurobipy import GRB
import numpy as np

def maximize_concurrent_flow(T, n=8, d=4):
    """
    Solves the Maximum Concurrent Flow problem for a given traffic matrix T
    using the hose model topology constraints.
    """
    # Initialize the Gurobi model
    model = gp.Model("Arbitrary_Traffic_Topology")
    
    # ---------------------------------------------------------
    # 2.1.1 Decision Variables
    # ---------------------------------------------------------
    
    # x_ij: Binary variable representing if a link exists from node i to node j
    x = model.addVars(n, n, vtype=GRB.BINARY, name="x")
    
    # f_ij^st: Continuous variable representing flow from source s to destination t 
    # that utilizes the link from i to j. (lower bound is 0.0 by default)
    f = model.addVars(n, n, n, n, vtype=GRB.CONTINUOUS, lb=0.0, name="f")
    
    # lambda: Continuous variable for the concurrent flow multiplier
    lam = model.addVar(vtype=GRB.CONTINUOUS, lb=0.0, name="lambda")
    
    # ---------------------------------------------------------
    # 2.1.2 Objective Function
    # ---------------------------------------------------------
    
    # Maximize the concurrent flow multiplier
    model.setObjective(lam, GRB.MAXIMIZE)
    
    # ---------------------------------------------------------
    # 2.1.3 Constraints
    # ---------------------------------------------------------
    
    # 1) Nodes cannot have connections to themselves
    for i in range(n):
        model.addConstr(x[i, i] == 0, name=f"no_self_loop_{i}")
        
    # 2) Every node must have exactly 'd' incoming and outgoing links
    for i in range(n):
        # Outgoing links = d
        model.addConstr(gp.quicksum(x[i, j] for j in range(n) if i != j) == d, name=f"out_degree_{i}")
        # Incoming links = d
        model.addConstr(gp.quicksum(x[j, i] for j in range(n) if i != j) == d, name=f"in_degree_{i}")
        
    # 3) Link Capacity: Total flow through link i->j cannot exceed x_ij (capacity of 1)
    for i in range(n):
        for j in range(n):
            if i != j:
                model.addConstr(
                    gp.quicksum(f[i, j, s, t] for s in range(n) for t in range(n) if s != t) <= x[i, j],
                    name=f"capacity_{i}_{j}"
                )
                
    # 4) Flow Conservation: Data must not appear or disappear
    for s in range(n):
        for t in range(n):
            if s != t:
                for u in range(n):
                    # Flow exiting node u for commodity (s,t)
                    out_flow = gp.quicksum(f[u, j, s, t] for j in range(n) if j != u)
                    # Flow entering node u for commodity (s,t)
                    in_flow = gp.quicksum(f[i, u, s, t] for i in range(n) if i != u)
                    
                    if u == s:
                        # If u is the source node
                        model.addConstr(out_flow - in_flow == lam * T[s][t], name=f"flow_src_{s}_{t}_{u}")
                    elif u == t:
                        # If u is the destination node
                        model.addConstr(out_flow - in_flow == -lam * T[s][t], name=f"flow_dst_{s}_{t}_{u}")
                    else:
                        # If u is an intermediate node
                        model.addConstr(out_flow - in_flow == 0, name=f"flow_mid_{s}_{t}_{u}")

    # ---------------------------------------------------------
    # Optimization and Results
    # ---------------------------------------------------------
    
    # Solve the model
    model.optimize()
    
    # Extract the resulting topology and lambda value if an optimal solution is found
    if model.status == GRB.OPTIMAL:
        topology = np.zeros((n, n), dtype=int)
        for i in range(n):
            for j in range(n):
                if x[i, j].X > 0.5:  # Checking > 0.5 prevents floating point precision issues
                    topology[i, j] = 1
        
        print(f"\nOptimal Concurrent Flow Multiplier (lambda): {lam.X:.4f}")
        return topology, lam.X
    else:
        print("\nNo optimal solution could be found for the given traffic matrix.")
        return None, None
    
if __name__ == "__main__":
    n = 8
    d = 4
    
    # 1. Create the Scaled Uniform Traffic Matrix
    T = np.zeros((n, n))
    
    # Each node sends 4/7 units of traffic to all 7 other nodes
    traffic_per_node = 4.0 / 7.0
    for i in range(n):
        for j in range(n):
            if i != j:
                T[i][j] = traffic_per_node
            
    print("--- Test Traffic Matrix (T) ---")
    print(np.round(T, 3))
    print("\nRunning Gurobi Solver...")
    
    # 2. Run the solver
    topology, max_lambda = maximize_concurrent_flow(T, n=n, d=d)
    
    # 3. Output results
    if topology is not None:
        print("\n--- Resulting Physical Topology ---")
        print(topology)
