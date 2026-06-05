import json
import argparse
import matplotlib.pyplot as plt
from collections import defaultdict

def load_discrete_data(file_path):
    """Load the discrete data from a JSON file"""
    with open(file_path, 'r') as f:
        data = json.load(f)
    return data

def analyze_agent_types(discrete_data):
    """Count and analyze agent types across all steps"""
    agent_types = {}
    
    # Use the first step to count agent types
    first_step = discrete_data[0]
    type_counts = defaultdict(int)
    
    for agent in first_step["agents"]:
        type_counts[agent["type"]] += 1
        agent_types[agent["agent_id"]] = agent["type"]
    
    print(f"Agent type distribution:")
    for agent_type, count in type_counts.items():
        print(f"  {agent_type}: {count} agents")
    
    return agent_types

def analyze_emotions(discrete_data):
    """Analyze emotion changes over time"""
    emotion_counts = []
    
    # Count emotions for each step
    for step_data in discrete_data:
        counts = defaultdict(int)
        for agent in step_data["agents"]:
            counts[agent["emotion"]] += 1
        emotion_counts.append(dict(counts))
    
    return emotion_counts

def plot_emotion_changes(emotion_counts):
    """Plot how emotions change over time"""
    # Extract all unique emotions
    all_emotions = set()
    for step_counts in emotion_counts:
        all_emotions.update(step_counts.keys())
    
    # Create a list of steps
    steps = list(range(len(emotion_counts)))
    
    # Create a dictionary to hold the count for each emotion at each step
    emotion_data = {emotion: [counts.get(emotion, 0) for counts in emotion_counts] 
                    for emotion in all_emotions}
    
    # Plot the data
    plt.figure(figsize=(12, 6))
    for emotion, counts in emotion_data.items():
        plt.plot(steps, counts, label=emotion)
    
    plt.xlabel('Step')
    plt.ylabel('Number of agents')
    plt.title('Emotion Changes Over Time')
    plt.legend()
    plt.grid(True)
    plt.savefig('emotion_changes.png')
    print("Saved emotion changes plot to emotion_changes.png")

def track_agent_movement(discrete_data, agent_id):
    """Track and display movement of a specific agent"""
    agent_positions = []
    
    for step_data in discrete_data:
        for agent in step_data["agents"]:
            if agent["agent_id"] == agent_id:
                agent_positions.append({
                    "step": step_data["step"],
                    "coordinate": agent["coordinate"],
                    "emotion": agent["emotion"],
                    "transport_method": agent["transport_method"]
                })
                break
    
    if not agent_positions:
        print(f"Agent {agent_id} not found in the data")
        return None
    
    return agent_positions

def plot_agent_path(agent_positions, agent_id):
    """Plot the path of an agent over time"""
    if not agent_positions:
        return
    
    # Extract coordinates
    lats = [pos["coordinate"]["lat"] for pos in agent_positions]
    lngs = [pos["coordinate"]["lng"] for pos in agent_positions]
    
    # Plot the path
    plt.figure(figsize=(10, 10))
    plt.plot(lngs, lats, 'b-', alpha=0.5)
    plt.scatter(lngs, lats, c=range(len(lngs)), cmap='viridis')
    plt.colorbar(label='Step')
    
    # Mark start and end points
    plt.scatter(lngs[0], lats[0], c='green', s=100, label='Start')
    plt.scatter(lngs[-1], lats[-1], c='red', s=100, label='End')
    
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title(f'Path of Agent {agent_id}')
    plt.legend()
    plt.grid(True)
    plt.savefig(f'agent_{agent_id}_path.png')
    print(f"Saved agent path plot to agent_{agent_id}_path.png")

def main():
    parser = argparse.ArgumentParser(description="Analyze discrete agent-based model data")
    parser.add_argument("-i", "--input", default="data/discrete_output.json", 
                        help="Input discrete JSON file path")
    parser.add_argument("-a", "--agent", default=None, 
                        help="Specific agent ID to track (optional)")
    
    args = parser.parse_args()
    
    # Load the discrete data
    print(f"Loading discrete data from {args.input}...")
    discrete_data = load_discrete_data(args.input)
    print(f"Loaded {len(discrete_data)} time steps")
    
    # Analyze agent types
    agent_types = analyze_agent_types(discrete_data)
    
    # Analyze emotions over time
    print("Analyzing emotion changes over time...")
    emotion_counts = analyze_emotions(discrete_data)
    plot_emotion_changes(emotion_counts)
    
    # Track a specific agent if requested
    if args.agent:
        print(f"Tracking agent {args.agent}...")
        agent_positions = track_agent_movement(discrete_data, args.agent)
        if agent_positions:
            plot_agent_path(agent_positions, args.agent)
            
            # Print some movement stats
            distance = 0
            for i in range(1, len(agent_positions)):
                prev = agent_positions[i-1]["coordinate"]
                curr = agent_positions[i]["coordinate"]
                # Simple Euclidean distance (not accurate for geographic coordinates but good enough for visualization)
                step_distance = ((curr["lat"] - prev["lat"]) ** 2 + (curr["lng"] - prev["lng"]) ** 2) ** 0.5
                distance += step_distance
            
            print(f"Agent {args.agent} traveled approximately {distance:.6f} coordinate units")
            print(f"Agent {args.agent} data sample:")
            print(json.dumps(agent_positions[0], indent=2))
    else:
        # If no specific agent is provided, suggest some
        print("\nTo track a specific agent, run the script with the -a/--agent flag, e.g.:")
        print(f"python analyze_discrete_data.py -a {list(agent_types.keys())[0]}")

if __name__ == "__main__":
    main() 