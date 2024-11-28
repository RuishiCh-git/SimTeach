import os
import random
import io
from flask import Flask, render_template, jsonify, request, send_file
from agents import agent_list
from llm_utils import *
from math_problems import PROBLEM_MAP

class Agent:
    def __init__(self, name, persona, task_schema=None):
        self.name = name 
        self.persona = persona
        self.task_schema = task_schema if task_schema is not None else {}
        self.character_schema = self._generate_character_schema()  # Generate schema here
        self.messages = []

    def _generate_character_schema(self):
        """
        Generate a personalized character schema for the agent using the shared task schema
        and potential mistakes, via the `create_character_schema` function.
        """
        if not self.task_schema:
            print(f"Warning: No task schema provided for {self.name}.")
            return {}

        try:
            self.character_schema = create_character_schema(self, self.task_schema, getattr(self, 'potential_mistakes', {}))
            if not self.character_schema:
                print(f"Warning: Failed to generate a character schema for {self.name}.")
                self.character_schema = {}  # Fallback to empty schema
        except Exception as e:
            print(f"Error generating character schema for {self.name}: {e}")
            self.character_schema = {}

        return self.character_schema


class Game:
    def __init__(self, agents, math_problem):
        self.math_problem = math_problem
        self.task_schema = self._generate_task_schema(math_problem)
        self.potential_mistakes = self._identify_potential_mistakes()
        self.public_messages = []
        self.gamestate = f"MATH PROBLEM: {self.math_problem}\n\nDISCUSSION SO FAR:\n"
        self.agent_reflections = {}  # Store reflections for each agent
        self.final_answers_sent = False  # Ensure this is initialized properly

        # Initialize agents
        self.agents = [
            Agent(agent_data.name, agent_data.persona, self.task_schema)
            for agent_data in agents
        ]

    def _generate_task_schema(self, math_problem):
        print(f"Generating task schema for problem: {math_problem}")
        task_schema = generate_task_schema(math_problem)
        if not task_schema:
            print("Failed to generate task schema. Using an empty schema as fallback.")
            return {}
        print(f"Generated task schema: {task_schema}")
        return task_schema

    def _identify_potential_mistakes(self):
        print("Identifying potential mistakes...")
        potential_mistakes = identify_potential_mistakes(self.task_schema)
        if not potential_mistakes:
            print("Failed to identify potential mistakes. Using an empty dictionary as fallback.")
            return {}
        print(f"Identified potential mistakes: {potential_mistakes}")
        return potential_mistakes

    def update_gamestate(self, agent_name, message, act):
        # Ensure the message format includes the agent's name
        formatted_message = f"{agent_name}: {message}"
        self.public_messages.append(formatted_message)  # Append to the discussion log
        self.gamestate = f"MATH PROBLEM: {self.math_problem}\n\nDISCUSSION SO FAR:\n" + "\n".join(self.public_messages)

    def instruct_agent(self, agent, act):
        system_prompt = f"""
        Generate a reply from {agent.name} based on the action and the variables from {agent.name}'s thought schema.
        Never mention the "task" word in the reply.

        Remember you're a middle school student, please reply in one sentence with the tone of a middle school student.
        Explain why you are taking the action "{act}" as part of the reply.

        The action to take is "{act}".
        
        Character Schema:
        {agent.character_schema}

        Current Discussion:
        {self.gamestate}

        OUTPUT FORMAT:
        Reasoning: [explain why you are taking this action]
        Response: [your one-sentence response as a middle school student]
        """
        
        messages = [{"role": "system", "content": system_prompt}]
        
        try:
            response = gen_oai(messages, model="gpt-4")
            
            # Parse the response to extract reasoning and message
            reasoning_match = re.search(r'Reasoning:\s*(.+)$', response, re.MULTILINE)
            response_match = re.search(r'Response:\s*(.+)$', response, re.MULTILINE)
            
            reasoning = reasoning_match.group(1).strip() if reasoning_match else "No reasoning provided."
            message = response_match.group(1).strip() if response_match else response.strip()

            # Debugging log
            print(f"ACT: {act}, Reasoning: {reasoning}, Message: {message}")
            
            return {
                "name": agent.name,
                "message": message,
                "reasoning": reasoning,
                "act": act
            }
        except Exception as e:
            print(f"Error: {e}")
            return {
                "name": agent.name,
                "message": "Error generating response.",
                "reasoning": "Unable to provide reasoning.",
                "act": act
            }


    def _create_system_prompt(self, agent, act):
        task_descriptions = "\n".join([f"Task {i+1}: {task['description']}" 
                                     for i, task in enumerate(self.task_schema.values())])
        
        conversation_history = "\n".join(self.public_messages[-3:]) if self.public_messages else "No messages yet."
        
        return f"""
        As {agent.name}, a {agent.persona}, respond to this math discussion.
        
        CONTEXT:
        Math Problem: {self.math_problem}
        Recent Messages:
        {conversation_history}
        
        Task Schema:
        {task_descriptions.strip()}
        
        Character Schema:
        {agent.character_schema}
        
        INSTRUCTIONS:
        1. Respond naturally as a middle school student
        2. Stay in character as {agent.name}
        3. Action required: {act}
        4. Keep responses very brief (1-2 sentences maximum)
        5. For final answers, clearly state your answer in this format: "My answer: [your answer]"
        6. No emojis or excessive punctuation
        """
    
    def clean_response(self, response):
        """Clean response text to make it more natural"""
        cleaned = response
        # Define response cleaning patterns
        CLEANUP_PATTERNS = [
            (r'\(Provide .*?\):', ''),
            (r'My answer:', ''),
            (r'My final answer:', ''),
            (r'^\s*\w+:', ''),  # Remove name prefixes
            (r'\s+', ' ')  # Clean up extra whitespace
        ]
        for pattern, replacement in CLEANUP_PATTERNS:
            cleaned = re.sub(pattern, replacement, cleaned)
        return cleaned.strip()

    def generate_reflection(self, agent):
        """Generate a reflection based on the conversation history"""
        reflection_prompt = f"""
        Based on {agent.name}'s contributions to the math discussion so far, 
        summarize their thought process and approach in 2-3 sentences.
        Consider their understanding, strategy, and interaction with others.
        
        Previous messages:
        {self.gamestate}
        """
        
        try:
            reflection = gen_oai([{"role": "system", "content": reflection_prompt}])
            return reflection
        except Exception as e:
            print(f"Error generating reflection: {e}")
            return "Unable to generate reflection."
        
    def run_round(self, current_round, total_rounds):
        """Improved round logic with better conversation flow"""
        round_data = []
        agents = self.agents[:]
        random.shuffle(agents)  # Randomize order each round
        
        for i, agent in enumerate(agents):
            # More natural conversation progression
            if current_round == 1 and i == 0:
                act = "Begin solving the problem"
            elif current_round == total_rounds - 1:
                act = "Provide final answer with explanation"
            else:
                # Choose contextual acts based on conversation state
                previous_messages = len(self.public_messages)
                if previous_messages < 2:
                    act = "Start approaching the problem"
                elif i == 0:
                    act = "Build on previous work"
                else:
                    acts = [
                        "Ask for clarification",
                        "Point out important details",
                        "Suggest next steps",
                        "Check for mistakes",
                        "Add to the discussion"
                    ]
                    act = random.choice(acts)
            
            response = self.instruct_agent(agent, act)
            self.update_gamestate(agent.name, response["message"], act)
            round_data.append(response)
            
        return round_data

    def get_final_answers(self):
        if self.final_answers_sent:  # Check if final answers have already been sent
            print("Final answers already sent. Skipping generation.")
            return []  # Return an empty list if already sent

        print("Fetching final answers...")
        final_answers = []
        for agent in self.agents:
            response = self.instruct_agent(agent, "final answer")
            message = response["message"]
            message = re.sub(r'.*?(My answer:|Provide final answer with explanation:)', '', message).strip()
            message = re.sub(f'^{agent.name}:\\s*', '', message).strip()
            final_answers.append({"name": agent.name, "answer": message})
        print(f"Final answers: {final_answers}")
        self.final_answers_sent = True  # Mark final answers as sent
        return final_answers


def init_game(agents=[], math_problem="Simplify the following, if possible: (m^2 + 2m - 3) / (m - 3)"):
    # Convert dict agents to Agent instances
    initialized_agents = [
        Agent(agent["name"], agent["persona"], agent.get("task_schema")) 
        for agent in agents
    ]
    return Game(initialized_agents, math_problem=math_problem)

app = Flask(__name__)
game = None
current_agent_index = 0
game_data = []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_simulation', methods=['POST'])
def start_simulation():
    global game, current_agent_index, game_data
    try:
        data = request.json
        
        problem_type = data.get('problem_type')
        if not problem_type:
            return jsonify({"error": "Problem type not provided"}), 400
        
        if problem_type not in PROBLEM_MAP:
            return jsonify({"error": "Invalid problem type"}), 400
        
        math_problem = PROBLEM_MAP[problem_type]['problem']
        
        # Initialize game with selected problem
        game = init_game(agents=agent_list, math_problem=math_problem)
        current_agent_index = 0
        game_data = []

        # Debugging: Ensure the game is initialized
        if game:
            print(f"Game initialized with math problem: {math_problem}")
        else:
            print("Failed to initialize game.")
        
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Error in start_simulation: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/add_agent', methods=['POST'])
def add_agent():
    global game
    data = request.json
    new_agent = Agent(name=data['name'], persona=data['persona'])
    math_problem = data.get('math_problem', "Simplify the following, if possible: (m^2 + 2m - 3) / (m - 3)")
    task_schema = generate_task_schema(math_problem)
    potential_mistakes = identify_potential_mistakes(task_schema)
    new_agent.character_schema = create_character_schema(new_agent, task_schema, potential_mistakes)
    agent_list.append({"name": new_agent.name, "persona": new_agent.persona, "character_schema": new_agent.character_schema})
    if game is None:
        game = init_game(agent_list, math_problem=math_problem)
    return jsonify({"status": "success"})

@app.route('/next_agent', methods=['POST'])
def next_agent():
    global current_agent_index, game_data, game
    data = request.json
    
    current_round = data.get('current_round')
    total_rounds = data.get('total_rounds')
    
    if current_round is None or total_rounds is None:
        return jsonify({"error": "Missing round information"}), 400

    if current_round < total_rounds:
        try:
            if current_agent_index == 0:
                round_data = game.run_round(current_round, total_rounds)
                game_data.extend(round_data)
            
            agent_data = game_data[current_agent_index]
            current_agent_index += 1
            
            round_finished = current_agent_index >= len(game.agents)
            if round_finished:
                current_agent_index = 0
                game_data = []
                current_round += 1
            
            return jsonify({
                "agent_data": {
                    "name": agent_data["name"],
                    "message": agent_data["message"],
                    "reasoning": agent_data["reasoning"],
                    "act": agent_data["act"]
                },
                "current_round": current_round,
                "round_finished": round_finished
            })
            
        except Exception as e:
            print(f"Error in next_agent: {e}")
            return jsonify({"error": str(e)}), 500
    else:
        final_answers = game.get_final_answers()
        return jsonify({
            "finished": True,
            "final_answers": final_answers
        })


@app.route('/download_log', methods=['GET'])
def download_log():
    if game and game.public_messages:  # Check if game and messages exist
        log_content = "MATH DISCUSSION LOG\n"
        log_content += "=" * 50 + "\n\n"
        
        # Add problem statement
        log_content += f"MATH PROBLEM:\n{game.math_problem}\n\n"
        
        # Add participants info
        log_content += "PARTICIPANTS:\n"
        for agent in game.agents:
            log_content += f"{agent.name}:\n"
            log_content += f"  Persona: {agent.persona}\n"
            log_content += f"  Character Schema: {json.dumps(agent.character_schema, indent=2)}\n\n"
        
        # Add discussion with reflections
        log_content += "DISCUSSION:\n"
        log_content += "=" * 50 + "\n\n"
        for i, message in enumerate(game.public_messages):
            log_content += f"[{i + 1}] {message}\n"
        
        # Create in-memory file
        mem_file = io.BytesIO()
        mem_file.write(log_content.encode())
        mem_file.seek(0)
        
        return send_file(
            mem_file,
            mimetype='text/plain',
            as_attachment=True,
            download_name='math_discussion.txt'
        )
    return jsonify({"error": "No discussion to download"})


@app.route('/reset', methods=['POST'])
def reset_game():
    global game, current_agent_index, game_data, agent_list
    agent_list = agent_list[:]
    game = None
    current_agent_index = 0
    game_data = []
    return jsonify({"status": "reset"})

if __name__ == "__main__":
    app.run(debug=True)
