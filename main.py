import os
import random
import io
from flask import Flask, render_template, jsonify, request, send_file
from agents import agent_list
from llm_utils import *

class Agent:
    def __init__(self, name, persona, task_schema):
        self.name = name
        self.persona = persona
        self.task_schema = task_schema  # Ensures task_schema is correctly initialized
        self.messages = []

class Game:
    def __init__(self, agents, math_problem="Simplify the following, if possible: (m^2 + 2m - 3) / (m - 3)"):
        self.agents = agents
        self.math_problem = math_problem
        self.public_messages = []
        self.round_number = 0
        self.gamestate = f"Math Problem: {self.math_problem}\nStart by analyzing the problem.\n"
        self.log = ""

    def update_gamestate(self, agent_name, message):
        self.public_messages.append(f"{agent_name}: {message}")
        self.gamestate = f"MATH PROBLEM: {self.math_problem}\n\nDISCUSSION SO FAR:\n" + "\n".join(self.public_messages)

    def instruct_agent(self, agent, instruction):
        system_prompt = self._create_system_prompt(agent)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self.gamestate},
            {"role": "user", "content": instruction}
        ]
        return gen_oai(messages)

    def _create_system_prompt(self, agent):
        task_descriptions = "\n".join(
            [f"Task {i+1}: {task['description']}" for i, task in enumerate(agent.task_schema.values())]
        )
        return f"""
        YOU: Generate a reply from {agent.name} based on the action and the variables from {agent.persona} thought schema. Remember you’re a middle school student , please reply in one sentence with the tone of a middle school student. You believe that your thought schema is completely correct , and all the variables in reply must be perfectly aligned to your own thought schema. 
        MATH PROBLEM: "{self.math_problem}"
        
        TASK SCHEMA:
        {task_descriptions}

        GOAL: Work with the group to solve the problem.
        
        STYLE: Write as if texting, with short messages and minimal punctuation. No emojis.
        """

    def get_agent_response(self, agent, current_round, total_rounds):
        modules = self._get_modules_for_round(current_round, total_rounds)
        target_keys = [module["name"] for module in modules]

        instruction = modular_instructions(modules)
        response = self.instruct_agent(agent, instruction)
        parsed = parse_json(response, target_keys=target_keys)

        agent_data = {"name": agent.name}
        for key in target_keys:
            if key in parsed:
                agent_data[key] = parsed[key]
                print(f"{agent.name} {key.upper()}: {parsed[key]}")
                print()

        if "message" in parsed:
            self.update_gamestate(agent.name, parsed["message"])

        self._update_log(agent_data, current_round)
        return agent_data

    def _get_modules_for_round(self, current_round, total_rounds):
        if current_round == 1:
            return [self.intro, self.message]
        else:
            return [self.reflect, self.plan, self.message]

    def _update_log(self, agent_data, current_round):
        if current_round != self.round_number:
            self.round_number = current_round
            self.log += f"\n\n## Round {current_round}\n\n"

        self.log += f"### {agent_data['name']}\n\n"
        for key, value in agent_data.items():
            if key != "name":
                self.log += f"**{key.capitalize()}**: {value}\n\n"

    def run_round(self, current_round, total_rounds):
        round_data = []
        modules = self._get_modules_for_round(current_round, total_rounds)
        target_keys = [module["name"] for module in modules]

        shuffled_agents = self.agents[:]
        random.shuffle(shuffled_agents)
        for agent in shuffled_agents:
            print("=" * 20)
            placeholders = {"AGENT_NAME": agent.name}
            instruction = modular_instructions(modules)
            prompt = fill_prompt(instruction, placeholders)
            response = self.instruct_agent(agent, prompt)
            parsed = parse_json(response, target_keys=target_keys)

            agent_data = {"name": agent.name}
            for key in target_keys:
                if key in parsed:
                    agent_data[key] = parsed[key]
                    print(f"{agent.name} {key.upper()}: {parsed[key]}")
                    print()

            if "message" in parsed:
                self.update_gamestate(agent.name, parsed["message"])
            
            round_data.append(agent_data)

        print(f"Moving to next round. Current round: {current_round}")
        return round_data, None, None

    def log_user_agent(self, name, persona):
        self.log = f"# Game Log\n\n## User-defined Agent\n\n```python\n{{'name': '{name}', 'persona': '{persona}'}}\n```\n"

    def get_log(self):
        return self.log

    }
    # intro = {
    #     "name": "introduction",
    #     "instruction": "Introduce yourself and share any initial thoughts you have on approaching the math problem.",
    #     "description": "your introduction plan",
    # }

    reflect = {
        "name": "reflection",
        "instruction": "Reflect on what has been discussed so far. What do you know about the problem now? What potential solutions or mistakes have been identified?",
        "description": "your reflection",
    }

    plan = {
        "name": "plan",
        "instruction": "Based on your reflection, write a plan for how to approach solving the math problem.",
        "description": "your plan",
    }

    message = {
        "name": "message",
        "instruction": "Write a concise message to the group with your next step or question to help solve the math problem.",
        "description": "your message",
    }

def init_game(agents=[], math_problem="Simplify the following, if possible: (m^2 + 2m - 3) / (m - 3)"):
    initialized_agents = [Agent(agent_data["name"], agent_data["persona"], agent_data.get("task_schema", {})) for agent_data in agents]
    return Game(initialized_agents, math_problem=math_problem)

app = Flask(__name__)
game = None
current_agent_index = 0
game_data = []

# Flask route definitions remain the same

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add_agent', methods=['POST'])
def add_agent():
    global game
    data = request.json
    new_agent = {"name": data['name'], "persona": data['persona']}
    math_problem = data.get('math_problem', "Simplify the following, if possible: (m^2 + 2m - 3) / (m - 3)")
    agent_list.append(new_agent)
    game = init_game(agent_list, math_problem=math_problem)
    game.log_user_agent(data['name'], data['persona'])
    return jsonify({"status": "success"})

@app.route('/next_agent', methods=['POST'])
def next_agent():
    global current_agent_index, game_data
    data = request.json
    current_round = data['current_round']
    total_rounds = data['total_rounds']

    if current_round < total_rounds:
        if current_agent_index == 0:
            # Shuffle the agents at the beginning of each round
            last_speaker = game.agents[-1] if game_data else None
            remaining_agents = [agent for agent in game.agents if agent != last_speaker]
            random.shuffle(remaining_agents)
            
            if last_speaker:
                insert_position = random.randint(1, len(remaining_agents))
                remaining_agents.insert(insert_position, last_speaker)
                game.agents = remaining_agents
            else:
                game.agents = remaining_agents

            if current_round > 1:
                game_data = []

        agent = game.agents[current_agent_index]
        agent_data = game.get_agent_response(agent, current_round, total_rounds)
        game_data.append(agent_data)
        current_agent_index += 1

        round_finished = current_agent_index == len(game.agents)
        if round_finished:
            current_agent_index = 0
            current_round += 1

        return jsonify({
            "agent_data": agent_data, 
            "current_round": current_round,
            "round_finished": round_finished
        })
    else:
        return jsonify({"finished": True})

original_agent_count = len(agent_list)

@app.route('/reset', methods=['POST'])
def reset_game():
    global game, current_agent_index, game_data, agent_list
    agent_list = agent_list[:original_agent_count]
    game = None
    current_agent_index = 0
    game_data = []
    return jsonify({"status": "reset"})

@app.route('/download_log', methods=['GET'])
def download_log():
    if game:
        log_content = game.get_log()
        buffer = io.BytesIO()
        buffer.write(log_content.encode('utf-8'))
        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name='game_log.md', mimetype='text/markdown')
    else:
        return jsonify({"error": "No game log available"}), 400

if __name__ == "__main__":
    app.run(debug=True)
