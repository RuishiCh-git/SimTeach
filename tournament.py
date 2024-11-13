import math
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from flask_socketio import SocketIO
from game import Game, Agent
from llm_utils import modular_instructions
from json import loads as parse_json

@dataclass
class TournamentMatch:
    """Represents a match in the tournament between two participants."""
    participant1: Optional[Agent]
    participant2: Optional[Agent]
    winner: Optional[Agent] = None
    votes: Optional[List[Tuple[str, str]]] = None
    conversation: str = ""
    is_active: bool = False

@dataclass
class AgentStats:
    """Tracks an agent's performance throughout the tournament."""
    name: str
    round_reached: int
    total_votes: int

def get_spectator_vote(
    spectator: Agent, 
    game: Game, 
    participant1: Agent, 
    participant2: Agent
) -> str:
    """Get a single spectator's vote after watching the conversation."""    
    instruction = f"""
    You must vote for either {participant1.name} or {participant2.name} to be {game.position}.
    Your response should be a JSON object with a single field "vote" containing ONLY the name of your choice.
    Example valid responses:
    {{"vote": "{participant1.name}"}}
    or
    {{"vote": "{participant2.name}"}}
    """
    response = game.instruct_agent(spectator, instruction)
    
    # Parse the JSON response
    parsed = parse_json(response)
    vote = parsed.get("vote", "").strip()
    
    if vote not in [participant1.name, participant2.name]:
        raise ValueError(f"Invalid vote from {spectator.name}: '{vote}'. Must be either '{participant1.name}' or '{participant2.name}'")
        
    return vote

class Tournament:
    def __init__(self, agents: List[Agent], position: str, socketio: SocketIO):
        """Initialize tournament with agents, position, and socketio for updates."""
        self.all_agents = agents
        self.position = position
        self.rounds: List[List[TournamentMatch]] = []
        self.agent_stats: Dict[str, AgentStats] = {
            agent.name: AgentStats(agent.name, 0, 0) 
            for agent in agents
        }
        self.thread_pool = ThreadPoolExecutor(max_workers=4)
        self.socketio = socketio
        
        self.setup_tournament_structure()
        self.emit_tournament_state()

    def setup_tournament_structure(self):
        """Creates the initial tournament structure with evenly distributed byes."""
        num_agents = len(self.all_agents)
        num_rounds = math.ceil(math.log2(num_agents))
        total_slots = 2 ** num_rounds
        num_byes = total_slots - num_agents
        
        # Create list of agents
        shuffled_agents = self.all_agents.copy()
        random.shuffle(shuffled_agents)
        
        # Create matches list with all slots
        matches = [(None, None)] * (total_slots // 2)
        
        # Calculate byes per half
        byes_per_half = num_byes // 2
        remaining_bye = num_byes % 2
        
        # Fill in byes for first half
        for i in range(byes_per_half):
            matches[i] = (None, shuffled_agents.pop())
        
        # Fill in byes for second half
        second_half_start = len(matches) // 2
        for i in range(byes_per_half + remaining_bye):
            matches[second_half_start + i] = (None, shuffled_agents.pop())
        
        # Fill remaining slots with agent pairs
        for i in range(len(matches)):
            if matches[i] == (None, None):
                if len(shuffled_agents) >= 2:
                    matches[i] = (shuffled_agents.pop(), shuffled_agents.pop())
        
        # Create first round
        first_round = []
        for p1, p2 in matches:
            match = TournamentMatch(p1, p2)
            first_round.append(match)
            
        self.rounds.append(first_round)
        
        # Set up subsequent rounds
        matches_in_round = len(first_round) // 2
        while matches_in_round >= 1:
            self.rounds.append([
                TournamentMatch(None, None) 
                for _ in range(matches_in_round)
            ])
            matches_in_round //= 2

    def emit_tournament_state(self):
        """Emits current tournament state to all clients."""
        # Get final round winner if tournament is complete
        final_winner = None
        if self.rounds[-1][0].winner:
            final_winner = self.rounds[-1][0].winner.name

        state = {
            "rounds": [
                [{
                    "participant1": m.participant1.name if m.participant1 else None,
                    "participant2": m.participant2.name if m.participant2 else None,
                    "winner": m.winner.name if m.winner else None,
                    "votes": m.votes,
                    "conversation": m.conversation,
                    "is_active": m.is_active
                } for m in round_matches]
                for round_matches in self.rounds
            ],
            "leaderboard": [
                {
                    "name": stats.name,
                    "round_reached": stats.round_reached,
                    "total_votes": stats.total_votes
                }
                for stats in sorted(
                    self.agent_stats.values(),
                    # Sort by: round reached, then winner status, then votes
                    key=lambda x: (
                        x.round_reached, 
                        1 if final_winner and x.name == final_winner else 0,
                        x.total_votes
                    ),
                    reverse=True
                )
            ]
        }
        self.socketio.emit('tournament_update', state)

    def run_match(self, match: TournamentMatch) -> Tuple[Agent, List[Tuple[str, str]]]:
        """Runs a single match and emits updates."""
        if match.participant1 is None:
            return match.participant2, []
        if match.participant2 is None:
            return match.participant1, []
        
        match.is_active = True
        self.emit_tournament_state()
        
        game = Game([match.participant1, match.participant2])
        game.position = self.position
        
        # Run 3 rounds of discussion between the two participants
        for current_round in range(1, 4):
            for agent in [match.participant1, match.participant2]:
                response = game.get_agent_response(agent, current_round, 3)
                match.conversation = game.gamestate
                self.emit_tournament_state()
                time.sleep(1)
        
        # Get all possible spectators
        spectators = [
            agent for agent in self.all_agents 
            if agent not in [match.participant1, match.participant2]
        ]
        
        # Randomly sample 9 spectators (or all if less than 9)
        num_voters = min(9, len(spectators))
        voting_spectators = random.sample(spectators, num_voters)
        
        votes = []
        vote_counts = {
            match.participant1.name: 0,
            match.participant2.name: 0
        }
        
        # Create spectator game with the full conversation
        spectator_game = Game([match.participant1, match.participant2])
        spectator_game.position = self.position
        spectator_game.gamestate = match.conversation
        
        print(f"\nCollecting votes for match between {match.participant1.name} and {match.participant2.name}:")
        
        # Get votes from sampled spectators
        for spectator in voting_spectators:
            try:
                vote = get_spectator_vote(spectator, spectator_game, match.participant1, match.participant2)
                votes.append((spectator.name, vote))
                vote_counts[vote] += 1
                match.votes = votes.copy()
                print(f"{spectator.name} voted for {vote}")
                self.emit_tournament_state()
            except Exception as e:
                print(f"Error getting vote from {spectator.name}: {e}")
        
        print(f"\nFinal vote counts: {vote_counts}")
        
        # Determine winner
        if vote_counts[match.participant1.name] == vote_counts[match.participant2.name]:
            winner = random.choice([match.participant1, match.participant2])
        else:
            winner_name = max(vote_counts.items(), key=lambda x: x[1])[0]
            winner = (match.participant1 
                     if winner_name == match.participant1.name 
                     else match.participant2)
        
        # Update stats
        for _, votee in votes:
            if votee in self.agent_stats:
                self.agent_stats[votee].total_votes += 1
        
        match.is_active = False
        self.emit_tournament_state()
        return winner, votes

    def run_round(self, round_index: int):
        """Runs all matches in a round in parallel."""
        current_round = self.rounds[round_index]
        
        # Update round reached for all participants
        for match in current_round:
            for participant in [match.participant1, match.participant2]:
                if participant and participant.name in self.agent_stats:
                    self.agent_stats[participant.name].round_reached = round_index + 1
        
        # Run all matches in parallel
        future_matches = []
        for i, match in enumerate(current_round):
            future = self.thread_pool.submit(self.run_match, match)
            future_matches.append((i, future))
        
        # Collect results and set up next round
        for i, future in future_matches:
            winner, votes = future.result()
            current_round[i].winner = winner
            current_round[i].votes = votes
            
            # Set up next round matches if not final round
            if round_index < len(self.rounds) - 1:
                next_match_index = i // 2
                if i % 2 == 0:
                    self.rounds[round_index + 1][next_match_index].participant1 = winner
                else:
                    self.rounds[round_index + 1][next_match_index].participant2 = winner
                self.emit_tournament_state()

    def run_tournament(self) -> Tuple[Agent, List[List[TournamentMatch]], List[AgentStats]]:
        """Runs tournament, emitting updates throughout."""
        for round_index in range(len(self.rounds)):
            self.run_round(round_index)
            
        final_match = self.rounds[-1][0]
        leaderboard = sorted(
            self.agent_stats.values(),
            key=lambda x: (x.round_reached, x.total_votes),
            reverse=True
        )
        return final_match.winner, self.rounds, leaderboard