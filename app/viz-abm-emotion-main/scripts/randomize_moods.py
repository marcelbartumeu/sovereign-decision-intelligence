import os
import json
import random
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def generate_random_mood_vector(size=7):
    """Generates a random probability distribution vector of a given size."""
    if size <= 0:
        return []
    
    random_values = [random.random() for _ in range(size)]
    total = sum(random_values)
    
    # Avoid division by zero if all random values are 0 (highly unlikely)
    if total == 0:
        # Return a uniform distribution
        return [1.0 / size] * size
    else:
        # Normalize to sum to 1
        return [value / total for value in random_values]

def process_agent_file(file_path):
    """Loads an agent file, randomizes mood vectors, and saves it back."""
    try:
        with open(file_path, 'r') as f:
            agent_data = json.load(f)
        
        logging.info(f"Processing file: {file_path}")
        
        if 'trips' in agent_data and isinstance(agent_data['trips'], list):
            for trip in agent_data['trips']:
                if 'mood_vectors' in trip and isinstance(trip['mood_vectors'], list):
                    num_vectors = len(trip['mood_vectors'])
                    if num_vectors > 0:
                        # Generate new random mood vectors for the trip
                        new_mood_vectors = [generate_random_mood_vector() for _ in range(num_vectors)]
                        trip['mood_vectors'] = new_mood_vectors
                        logging.debug(f"  Randomized {num_vectors} mood vectors for trip_id {trip.get('trip_id', 'N/A')}")
                    else:
                         logging.debug(f"  No mood vectors found for trip_id {trip.get('trip_id', 'N/A')}")
                else:
                    logging.warning(f"  'mood_vectors' key missing or not a list in a trip for file: {file_path}")

            # Save the modified data back to the file
            with open(file_path, 'w') as f:
                json.dump(agent_data, f, indent=2) # Use indent=2 for readability
            logging.info(f"Successfully updated and saved: {file_path}")
            
        else:
            logging.warning(f"'trips' key missing or not a list in file: {file_path}")

    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from file: {file_path}")
    except IOError as e:
        logging.error(f"File I/O error with {file_path}: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred while processing {file_path}: {e}")


def main():
    simulation_output_dir = 'src/simulation_output'
    if not os.path.isdir(simulation_output_dir):
        logging.error(f"Directory not found: {simulation_output_dir}")
        return

    logging.info(f"Starting mood vector randomization in directory: {simulation_output_dir}")

    for filename in os.listdir(simulation_output_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(simulation_output_dir, filename)
            if os.path.isfile(file_path):
                process_agent_file(file_path)

    logging.info("Finished processing all JSON files.")

if __name__ == "__main__":
    main() 