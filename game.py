"""Core game logic and agent classes for the tournament system."""
from llm_utils import *

class Agent:
    def __init__(self, name, persona):
        self.name = name
        self.persona = persona
        self.messages = []

class Game:
    def __init__(self, agents):
        self.agents = agents
        self.position = "group leader"
        self.public_messages = []
        self.round_number = 0
        self.winner = ""
        self.gamestate = "Nothing has been said yet. Start the conversation. You don't know anything about the other people in the group yet, and vice versa.\n"
        self.log = ""

    def update_gamestate(self, agent_name, message):
        self.public_messages.append(f"{agent_name}: {message}")
        self.gamestate = "\n".join(self.public_messages)

    def instruct_agent(self, agent, instruction):
        system_prompt = f"""
        YOU: You are {agent.name}, {agent.persona}. Speak in character as {agent.name} with very short messages in a conversational tone. """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": self.gamestate},
            {"role": "user", "content": instruction}
        ]
        return gen_oai(messages)

    def _create_system_prompt(self, agent):
        return f"""
        YOU: You are {agent.name}, {agent.persona}. Speak in character as {agent.name} with very short messages in a conversational tone. 
        
        SCENARIO: You are in a competition with one other person to become the {self.position}. Advocate for yourself to become the {self.position} by emphasizing your strengths and your opponent's weaknesses. At the end of the discussion, a group of people will vote for either you or your opponent.
        
        STYLE: Write in the style of someone texting, with short messages and minimal punctuation. No emojis. Speak in your own personal voice. Don't use generic or vague language."""

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
        elif current_round == total_rounds:
            return [self.reflect, self.plan, self.final_message]
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

    def get_log(self):
        return self.log

    intro = {
        "name": "introduction",
        "instruction": "Because the conversation has just started, you need to introduce themselves. Create a plan for a compelling introduction. Be creative in order to craft the most strategic introduction.",
        "description": "your introduction plan",
    }

    reflect = {
        "name": "reflection",
        "instruction": "Reflect on the situation by answering each of the following questions.\n1] Knowledge: What do you know so far about the opponent?\n2] Support: You will advocate for yourself to become the !<POSITION>! -- what are the pros and cons of yourself versus your opponent? If not much has been said yet, you can ask your opponent to share their answer to a question.",
        "description": "your reflection",
    }

    plan = {
        "name": "plan",
        "instruction": "Based on your reflection, write a plan for how you will persuade the audience to vote for you. Your message should be a focused argument that will help you gather more information about the opponent or persuade the group to vote for you. Remember that only one person can win.",
        "description": "your plan",
    }

    message = {
        "name": "message",
        "instruction": "Write your 2-4 sentence message to the audience, incorporating your plan from above. Make sure your message is RESPONSIVE: reference and respond to what has previously been said, answer any questions that were directed towards you, and make sure the conversation flows naturally.",
        "description": "your message",
    }

    vote_plan = {
        "name": "vote_plan",
        "instruction": "The conversation has ended, and it is time to think about who you will vote for. Think step-by-step: first list the pros and cons of each person (excluding yourself, as you cannot vote for yourself), then compare them against the things you value most. Provide your reasoning in this step.",
        "description": "your vote",
    }

    vote = {
        "name": "vote",
        "instruction": "The conversation has ended. Write a vote for the person you think should be the !<POSITION>!. You cannot vote for yourself, even if others support you. Respond with ONLY the name of the person you vote for.",
        "description": "your vote",
    }

    spectator_vote_plan = {
        "name": "vote_plan",
        "instruction": "You've watched a conversation between two candidates competing to be !<POSITION>!. Think step-by-step about who deserves your vote: first list the pros and cons of each candidate based on their discussion, then evaluate their qualifications, communication style, and leadership potential shown in the conversation.",
        "description": "your voting analysis",
    }

    spectator_vote = {
        "name": "vote",
        "instruction": "Based on the conversation you've watched between the candidates, who do you think should be the !<POSITION>!? Respond with ONLY the name of the person you vote for.",
        "description": "your vote",
    }

    final_message = {
        "name": "message",
        "instruction": "This is your final message in this match. Make a compelling closing statement to convince the audience to vote for you. Summarize your key strengths and qualifications for being !<POSITION>!, and make a clear call to action. Keep it concise but impactful.",
        "description": "your final message",
    } 