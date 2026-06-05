import json
import math
import copy
import argparse
from collections import defaultdict

def interpolate_position(start_pos, end_pos, progress):
    """Linear interpolation between two positions based on progress (0.0 to 1.0)"""
    return {
        "lat": start_pos["lat"] + (end_pos["lat"] - start_pos["lat"]) * progress,
        "lng": start_pos["lng"] + (end_pos["lng"] - start_pos["lng"]) * progress
    }

def transform_to_discrete(input_file, output_file, num_steps, include_all_fields=False):
    """
    Transform continuous agent data to discrete time steps.
    
    Parameters:
    - input_file: Path to input JSON file with continuous agent data
    - output_file: Path to output JSON file for discrete data
    - num_steps: Number of discrete steps to generate
    - include_all_fields: Whether to include all fields from original data or just a subset
    """
    print(f"Processing {input_file}...")
    
    # First pass: determine min and max timestamps
    min_timestamp = float('inf')
    max_timestamp = float('-inf')
    line_count = 0
    error_count = 0
    
    with open(input_file, 'r') as f:
        for line in f:
            line_count += 1
            try:
                data = json.loads(line.strip())
                min_timestamp = min(min_timestamp, data["timestamp"])
                max_timestamp = max(max_timestamp, data["timestamp"])
            except json.JSONDecodeError:
                error_count += 1
                print(f"Warning: Failed to parse JSON on line {line_count}")
                continue
    
    if line_count == error_count:
        raise ValueError("Failed to parse any valid JSON lines from the input file")
    
    time_range = max_timestamp - min_timestamp
    step_size = time_range / num_steps
    
    print(f"Time range: {time_range:.2f} seconds")
    print(f"Step size: {step_size:.2f} seconds")
    print(f"Parsed {line_count - error_count} valid entries, {error_count} errors")
    
    # Second pass: process data and organize by agent
    agent_events = defaultdict(list)
    agent_types = {}  # Store agent type information
    
    with open(input_file, 'r') as f:
        for line in f:
            try:
                data = json.loads(line.strip())
                agent_events[data["agent_id"]].append(data)
                
                # Store agent type if not already stored
                if data["agent_id"] not in agent_types:
                    agent_types[data["agent_id"]] = data["type"]
                    
            except json.JSONDecodeError:
                continue
    
    # Sort events by timestamp for each agent
    for agent_id in agent_events:
        agent_events[agent_id].sort(key=lambda x: x["timestamp"])
    
    print(f"Found {len(agent_events)} unique agents")
    
    # Generate discrete steps
    discrete_data = []
    
    for step in range(num_steps):
        step_time = min_timestamp + step * step_size
        step_data = []
        
        for agent_id, events in agent_events.items():
            # Find the events before and after this step time
            before_event = None
            after_event = None
            
            for event in events:
                if event["timestamp"] <= step_time:
                    before_event = event
                else:
                    after_event = event
                    break
            
            if before_event is None:
                # This step is before the agent's first event, skip
                continue
            
            position = None
            
            if after_event is None or before_event["transport_method"] == "stopped":
                # Either this is the agent's last event or the agent is stopped
                position = before_event["coordinate"]
            else:
                # Agent is moving, interpolate position
                if "new_coordinate" in before_event:
                    start_pos = before_event["coordinate"]
                    end_pos = before_event["new_coordinate"]
                    total_time = before_event["transport_minutes"] * 60  # Convert to seconds
                    
                    # Calculate how far along the route the agent is at this step
                    elapsed_time = step_time - before_event["timestamp"]
                    
                    if elapsed_time >= total_time:
                        # Agent has reached the destination
                        position = end_pos
                    else:
                        # Agent is somewhere along the route
                        progress = elapsed_time / total_time if total_time > 0 else 1.0
                        position = interpolate_position(start_pos, end_pos, progress)
                else:
                    # No movement information, use last known position
                    position = before_event["coordinate"]
            
            if position:
                # Create agent state for this step
                if include_all_fields:
                    # Include all original fields
                    agent_state = copy.deepcopy(before_event)
                    agent_state["step"] = step
                    agent_state["coordinate"] = position
                    # Remove fields that don't make sense in discrete format
                    for field in ["new_coordinate", "route_distance", "transport_minutes", "stop_time"]:
                        if field in agent_state:
                            del agent_state[field]
                else:
                    # Just include essential fields
                    agent_state = {
                        "agent_id": agent_id,
                        "step": step,
                        "type": before_event["type"],
                        "emotion": before_event["emotion"],
                        "transport_method": before_event["transport_method"],
                        "coordinate": position,
                        "mood_vector": before_event["mood_vector"]
                    }
                step_data.append(agent_state)
        
        # Add all agents for this step to the discrete data
        discrete_data.append({
            "step": step,
            "timestamp": step_time,
            "agents": step_data
        })
    
    # Write the transformed data
    with open(output_file, 'w') as f:
        json.dump(discrete_data, f, indent=2)
    
    print(f"Transformation complete. Output written to {output_file}")
    print(f"Generated {num_steps} discrete steps")

def main():
    parser = argparse.ArgumentParser(description="Transform continuous agent data to discrete time steps")
    parser.add_argument("-i", "--input", default="data/output.json", help="Input JSON file path")
    parser.add_argument("-o", "--output", default="data/discrete_output.json", help="Output JSON file path")
    parser.add_argument("-n", "--num-steps", type=int, default=500, help="Number of discrete steps to generate")
    parser.add_argument("--include-all-fields", action="store_true", help="Include all original data fields")
    
    args = parser.parse_args()
    
    transform_to_discrete(
        args.input, 
        args.output, 
        args.num_steps,
        args.include_all_fields
    )

if __name__ == "__main__":
    main() 