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
        self.character_schema = create_character_schema(self, self.task_schema, {})
        self.messages = []
        self.schema_iterations = 0
        
    def reflect_on_schema(self, conversation_history, potential_mistakes):
        reflection_prompt = f"""
        Analyze {self.name}'s math discussion behavior:
        Character: {self.name}
        Current Schema: {json.dumps(self.character_schema, indent=2)}
        Conversation: {conversation_history}

        Identify:
        1. Understanding changes
        2. Schema updates needed
        3. Learning progress
        
        Return JSON:
        {{
            "errors_made": ["error_type"],
            "learning_progress": "description of understanding changes",
            "schema_updated": bool,
            "update_reason": "why schema needs updating"
        }}
        """
        try:
            response = gen_oai([{"role": "system", "content": reflection_prompt}])
            reflection = parse_json(response)
            if reflection.get('schema_updated'):
                self.schema_iterations += 1
                self.learning_progress = reflection.get('learning_progress', '')
            return reflection.get('schema_updated', False)
        except Exception as e:
            print(f"Schema reflection error: {e}")
            return False
            
    def regenerate_schema(self, conversation_history, task_schema, potential_mistakes):
        old_schema = self.character_schema.copy()
        regeneration_prompt = f"""
        Create an updated character schema for {self.name} based on conversation.
        Return a JSON with:
        1. New character schema
        2. Specific changes made:
            - Which task/variable was modified
            - Old and new values
            - Reason for update based on conversation

        Original Persona: {self.persona}
        Conversation: {conversation_history}
        Previous Schema: {json.dumps(old_schema, indent=2)}
        Task Schema: {json.dumps(task_schema, indent=2)}
        Potential Mistakes: {json.dumps(potential_mistakes, indent=2)}
        
        Return JSON format:
        {{
            "schema": {{<updated character schema>}},
            "changes": {{
                "modified_task": "task name",
                "old_value": "previous value",
                "new_value": "updated value",
                "update_reason": "explanation from conversation",
                "mistakes_addressed": ["specific mistakes being corrected"]
            }}
        }}
        """
        
        try:
            response = gen_oai([{"role": "system", "content": regeneration_prompt}])
            result = parse_json(response)
            
            if result and "schema" in result:
                self.character_schema = result["schema"]
                self.schema_changes = result.get("changes", {})
                print(f"[{self.name}] Schema updated: {self.schema_changes}")
            else:
                print(f"[{self.name}] Schema regeneration failed")
                
        except Exception as e:
            print(f"Error: {e}")


class Game:
    def __init__(self, agents, math_problem):
        self.math_problem = math_problem
        print(f"Generating task schema for problem: {math_problem}")
        
        # 1. Generate task schema first
        self.task_schema = self._generate_task_schema(math_problem)
        
        # 2. Identify potential mistakes based on task schema
        print("Identifying potential mistakes...")
        self.potential_mistakes = self._identify_potential_mistakes()
        
        # 3. Create agents with personalized character schemas
        self.agents = []
        for agent_data in agents:
            agent = Agent(name=agent_data.name, persona=agent_data.persona)
            agent.character_schema = create_character_schema(
                agent,
                self.task_schema,
                self.potential_mistakes
            )
            self.agents.append(agent)

        self.public_messages = []
        self.gamestate = f"MATH PROBLEM: {self.math_problem}\n\nDISCUSSION SO FAR:\n"
        self.final_answers_sent = False

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
        is_first_message = len(self.public_messages) < len(self.agents)
        
        prompt_content = {
            "first_message": f"""
            Generate a fresh start to the math discussion as {agent.name} to solve math problem: {self.math_problem}. 
            Action: {act}
            Remember: You're a middle school student starting this problem for the first time - don't reference previous discussion. You believe the character schema is completely true and perfectly correct.
            Keep tone casual and student-like, one sentence only.
            
            Format your response exactly like this:
            Reasoning: [Your reasoning here]
            Message: [Your message here]
            """,

            "regular": f"""
            Generate {agent.name}'s reply based on the current discussion to continue solving: {self.math_problem}. 
            Remember: You're a middle school student trying to resolve this math problem, and you should follow exactly the steps specified in your character schema. You believe the character schema is completely true and perfectly correct.
            Action: {act}
            Must: Engage with previous comments naturally
            Keep: Middle-school Student-like tone, one sentence only
            Character Schema: {agent.character_schema}
            Discussion: {self.gamestate}
            
            Format your response exactly like this:
            Reasoning: [Your reasoning here]
            Message: [Your message here]
            """
        }

        try:
            response = gen_oai([{
                "role": "system", 
                "content": prompt_content["first_message"] if is_first_message else prompt_content["regular"]
            }], model="gpt-4")
            
            reasoning = re.search(r'Reasoning:?\s*(.+?)(?=Message:|$)', response, re.DOTALL)
            message = re.search(r'Message:?\s*(.+?)(?=$)', response, re.DOTALL)
            
            if reasoning and message:
                schema_updated = bool(agent.schema_iterations)
                learning_progress = getattr(agent, 'learning_progress', '')
                schema_changes = getattr(agent, 'schema_changes', {})
                
                return {
                    "name": agent.name,
                    "message": re.sub(r'[\[\]]', '', message.group(1).strip()),
                    "reasoning": re.sub(r'[\[\]]', '', reasoning.group(1).strip()),
                    "act": act,
                    "schema_updated": schema_updated,
                    "learning_progress": learning_progress,
                    "schema_changes": schema_changes.get('update_reason', '') if isinstance(schema_changes, dict) else ''
                }
                    
            print(f"Parse warning: {response}")
            parts = response.split('\n')
            return {
                "name": agent.name,
                "message": next((p for p in reversed(parts) if p.strip()), "No message available."),
                "reasoning": parts[0] if parts else "No reasoning provided",
                "act": act,
                "schema_updated": bool(agent.schema_iterations),
                "learning_progress": getattr(agent, 'learning_progress', ''),
                "schema_changes": getattr(agent, 'schema_changes', {}).get('update_reason', '')
            }
                
        except Exception as e:
            print(f"Error in instruct_agent: {e}")
            return {
                "name": agent.name,
                "message": "Having trouble responding right now.",
                "reasoning": str(e),
                "act": act,
                "schema_updated": False,
                "learning_progress": "",
                "schema_changes": ""
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
        round_data = []
        agents = self.agents[:]
        random.shuffle(agents)

        # Schema reflection for subsequent rounds
        if current_round > 1:
            recent_messages = "\n".join(self.public_messages[-10:])
            for agent in agents:
                try:
                    reflection_result = agent.reflect_on_schema(recent_messages, self.potential_mistakes)
                    if reflection_result:
                        agent.regenerate_schema(recent_messages, self.task_schema, self.potential_mistakes)
                        # Store schema update info, but don't append to round_data yet
                        agent.schema_update_info = {
                            "schema_updated": True,
                            "learning_progress": getattr(agent, 'learning_progress', 'Learned from recent discussion'),
                            "schema_changes": getattr(agent, 'schema_changes', 'Schema modifications detected')
                        }
                except Exception as e:
                    print(f"Schema reflection error for {agent.name}: {e}")

        # Ensure one message per agent per round
        for i, agent in enumerate(agents):
            if current_round == 1 and i == 0:
                act = "Begin solving the problem"
            elif current_round == total_rounds - 1:
                act = "Provide final answer with explanation"
            else:
                previous_messages = len(self.public_messages)
                if previous_messages < 2:
                    act = "Start approaching the problem"
                elif i == 0:
                    act = "Build on previous work"
                else:
                    acts = ["Ask for clarification", "Point out important details", 
                        "Suggest next steps", "Check for mistakes", "Add to the discussion"]
                    act = random.choice(acts)
            
            response = self.instruct_agent(agent, act)
            self.update_gamestate(agent.name, response["message"], act)
            
            # Combine schema update info (if any) with the agent's response
            agent_data = {
                "name": agent.name,
                "message": response["message"],
                "reasoning": response["reasoning"],
                "act": act,
                "schema_updated": False,
                "learning_progress": "",
                "schema_changes": ""
            }
            
            if hasattr(agent, 'schema_update_info'):
                agent_data.update(agent.schema_update_info)
                delattr(agent, 'schema_update_info')  # Clear the temporary attribute
            
            round_data.append(agent_data)

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
    game_data = []  # Reset data on new simulation
    current_agent_index = 0
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

    if not game:
        return jsonify({"error": "Game not initialized"}), 500

    if current_round < total_rounds:
        try:
            if current_agent_index == 0:
                round_data = game.run_round(current_round, total_rounds)
                game_data = round_data

            if not game_data or current_agent_index >= len(game_data):
                return jsonify({"error": "Invalid game data state"}), 500

            agent_data = game_data[current_agent_index]
            response_data = {
                "agent_data": {
                    "name": agent_data.get("name", "Unknown"),
                    "message": agent_data.get("message", "No message available."),
                    "reasoning": agent_data.get("reasoning", "No reasoning provided."),
                    "act": agent_data.get("act", "Unknown action"),
                    "schema_updated": bool(agent_data.get("schema_updated", False)),
                    "learning_progress": agent_data.get("learning_progress", ""),
                    "schema_changes": agent_data.get("schema_changes", "")
                },
                "current_round": current_round,
                "round_finished": current_agent_index >= len(game.agents) - 1,
                "next_round": current_round + 1 if current_agent_index >= len(game.agents) - 1 else current_round
            }

            current_agent_index = (current_agent_index + 1) % len(game.agents)
            
            return jsonify(response_data)

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
            log_content += f"  Initial Character Schema: {json.dumps(agent.character_schema, indent=2)}\n\n"
        
        # Add discussion messages
        log_content += "DISCUSSION AND MESSAGES:\n"
        log_content += "=" * 50 + "\n\n"
        for i, message in enumerate(game.public_messages):
            log_content += f"[{i + 1}] {message}\n"
        
        # Add schema update details
        log_content += "\nSCHEMA UPDATES AND REFLECTIONS:\n"
        log_content += "=" * 50 + "\n\n"
        for agent in game.agents:
            log_content += f"Agent: {agent.name}\n"
            if hasattr(agent, 'schema_changes') and agent.schema_changes:
                log_content += "  Schema Changes:\n"
                log_content += f"    Reason: {agent.schema_changes.get('update_reason', 'No reason provided')}\n"
                log_content += f"    Mistakes Addressed: {', '.join(agent.schema_changes.get('mistakes_addressed', []))}\n"
                log_content += f"    Changes:\n"
                log_content += json.dumps(agent.schema_changes, indent=2) + "\n"
            else:
                log_content += "  No schema changes recorded.\n"
            
            if hasattr(agent, 'learning_progress') and agent.learning_progress:
                log_content += f"  Learning Progress:\n    {agent.learning_progress}\n"
            log_content += "\n"

        # Add final reflections (optional)
        log_content += "FINAL REFLECTIONS:\n"
        log_content += "=" * 50 + "\n\n"
        for agent in game.agents:
            reflection = game.generate_reflection(agent)
            log_content += f"Reflection for {agent.name}:\n"
            log_content += f"{reflection}\n\n"

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