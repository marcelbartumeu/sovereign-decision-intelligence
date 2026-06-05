import json
import os
import random

def add_random_conversations_to_agents(directory, num_conversations=3):
    """
    Adds random conversations and timestamps to agent JSON files in a directory.

    Args:
        directory (str): The path to the directory containing agent JSON files.
        num_conversations (int): The number of conversations to add to each agent.
    """
    sayings = [
    "What a day!",
    "Hmm, where should I go next?",
    "Almost there.",
    "Feeling pretty good.",
    "Need a break.",
    "Is it lunch time yet?",
    "This city is bustling.",
    "Hope the traffic isn't too bad.",
    "Just enjoying the walk.",
    "Wonder what's new around here.",
    "Nice weather today.",
    "Need to remember to pick up groceries.",
    "Oh, look at that!",
    "Thinking about that meeting later.",
    "Let's take a different route.",
    "I should call them back.",
    "Where did the time go?",
    "Getting hungry.",
    "This reminds me of...",
    "Almost forgot my keys!",

    # Local flavor
    "Should I grab trinxat or a quick bocata?",
    "Clouds are rolling down from the mountains again.",
    "Gotta stop by that bookshop near the center.",
    "Smells like someone's making pho.",
    "Maybe I'll cut through the park.",
    "Those sunset colors over the valley... unreal.",
    "I should grab a milk tea while I'm here.",
    "Feels like everyone's out today.",
    "So many dogs around here!",
    "Parking's a nightmare, as usual.",
    "The corner bakery has that amazing garlic bread.",
    "Is that line for dumplings or donuts?",
    "Feels like the weekend already.",
    "I always get turned around near the old town lanes.",
    "Gotta beat the lunch crowd.",
    "Ugh, stepped in eucalyptus again.",
    "This fog has me in my feelings.",
    "Why do I always crave noodles here?",
    "Should I walk up to the old town or take the bus?",
    "Hearing four languages in two blocks — I love this city.",
    "Korean BBQ for dinner? Tempting.",
    "Did I just walk past that guy twice?",
    "Forgot how steep that block is.",
    "Oh nice, free books again.",
    "Is that a new mural?",
    "Need to hit the farmer's market on Sunday.",
    "The fog makes everything feel like a dream.",
    "I could really go for some Hokkaido milk soft serve.",
    "Why is it always windier on this side of the street?",
    "Someone's blasting jazz from their window again.",
    "That cat's always in the same window.",
    "The old town feels like its own little city.",
    "I swear I just smelled five different cuisines.",
    "Let's loop around the park before heading back.",
    "These houses have such character.",
    "I love how quiet it gets near the river.",
    "No idea where this path goes, but I'm following it.",
    "Should've brought a jacket... again.",
    "Why are the best dumplings always cash only?",
    "Tempted to sit and people-watch for a bit.",
    "I wonder what that shop sells — never seen it open.",
    "It's never just one quick stop in Avinguda Meritxell.",
    "I always forget how green this neighborhood is.",

    # Tourist / visitor vibes
    "This isn't what I pictured Andorra la Vella to look like.",
    "How is this just a neighborhood and not a whole city?",
    "Should I check out that bookstore or that bakery?",
    "There's a temple hidden back here? No way.",
    "This street smells like garlic and incense. I love it.",
    "Wait, is this Parc Central or the old quarter?",
    "I could get used to this fog.",
    "The hills here are no joke.",
    "This place has a kind of quiet magic.",
    "How did I end up walking 10k steps already?",
    "So many tiny businesses tucked into corners.",
    "These houses look like they're from a storybook.",
    "Is that a sushi place... next to a Russian bakery?",
    "Every other block feels like a different country.",
    "I wish I had more time to explore."

    # Tech / oddball / reflective
    "I should be coding, but this walk is worth it.",
    "This is giving real 'main character energy'.",
    "My algorithm would not predict this route.",
    "What if I just never go back to the office?",
    "This fog is like a soft filter on reality.",
    "I should really touch grass more often.",
    "Someone should train a model on these smells.",
    "So peaceful, I forgot I have 47 unread emails.",
    "You can feel the layers of stories here.",
    "This walk is better than therapy.",
    "Is there a startup idea in local walks?",
    "Everyone looks like they're on their own quest.",
    "The city feels like it's thinking too.",
    "I always forget how much I like walking here.",
    "This neighborhood has main character energy.",
    ]

    try:
        all_files = os.listdir(directory)
    except FileNotFoundError:
        print(f"Error: Directory not found: {directory}")
        return
    except Exception as e:
        print(f"Error listing directory {directory}: {e}")
        return

    agent_files = [f for f in all_files if f.startswith("agent_") and f.endswith(".json")]

    print(f"Found {len(agent_files)} agent files in {directory}")

    for filename in agent_files:
        filepath = os.path.join(directory, filename)
        print(f"Processing {filename}...")

        try:
            with open(filepath, 'r') as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print(f"  Skipping {filename}: Invalid JSON.")
                    continue

            all_timestamps = []
            if "trips" in data and isinstance(data["trips"], list):
                for trip in data.get("trips", []):
                     # Check if trip is a dictionary and has 'timestamps'
                    if isinstance(trip, dict) and "timestamps" in trip and isinstance(trip["timestamps"], list):
                        all_timestamps.extend(trip["timestamps"])
                    else:
                         # Log if a trip is malformed or missing timestamps
                         trip_id = trip.get("trip_id", "unknown") if isinstance(trip, dict) else "unknown"
                         print(f"  Warning: Trip {trip_id} in {filename} is missing 'timestamps' list or is not a dictionary.")


            if not all_timestamps:
                print(f"  Skipping {filename}: No timestamps found in trips.")
                continue

            min_time = min(all_timestamps)
            max_time = max(all_timestamps)

            if min_time >= max_time:
                 print(f"  Skipping {filename}: Cannot generate random timestamps (min_time >= max_time).")
                 continue


            # Ensure we don't request more sayings than available
            actual_num_conversations = min(num_conversations, len(sayings))
            if actual_num_conversations < num_conversations:
                 print(f"  Warning: Requested {num_conversations} conversations, but only {len(sayings)} unique sayings are available. Using {actual_num_conversations}.")


            conversation_times = sorted(random.sample(range(min_time, max_time + 1), actual_num_conversations))
            conversation_texts = random.sample(sayings, actual_num_conversations)

            data["conversation"] = conversation_texts
            data["conversation_timestamps"] = conversation_times

            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2) # Use indent=2 for readability
            print(f"  Added {actual_num_conversations} conversations to {filename}.")

        except FileNotFoundError:
            print(f"  Skipping {filename}: File not found during processing (unexpected).")
        except Exception as e:
            print(f"  Skipping {filename}: An error occurred: {e}")

# --- Configuration ---
TARGET_DIRECTORY = "src/simulation_output"
NUM_CONVERSATIONS_PER_AGENT = 3
# --- Run the script ---
add_random_conversations_to_agents(TARGET_DIRECTORY, NUM_CONVERSATIONS_PER_AGENT)

print("\nScript finished.")