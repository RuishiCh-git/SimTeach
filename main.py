import os
import random
import io
from flask import Flask, render_template, jsonify, request, send_file
from agents import agent_list
from llm_utils import *
from game import Game, Agent
from tournament import Tournament
from flask_socketio import SocketIO
import atexit

def init_game(agents=[]):
  initialized_agents = [Agent(agent_data["name"], agent_data["persona"]) for agent_data in agents]
  return Game(initialized_agents)

app = Flask(__name__)
socketio = SocketIO(app)

game = init_game(agent_list)
game.position = "group leader"

@app.route('/')
def index():
  return render_template('index.html')

@app.route('/tournament')
def tournament_page():
  return render_template('tournament.html')

@app.route('/run_tournament', methods=['POST'])
def run_tournament():
  tournament = Tournament(game.agents, game.position, socketio)
  winner, rounds, leaderboard = tournament.run_tournament()
  return jsonify({"status": "complete"})

@app.route('/reset', methods=['POST'])
def reset_game():
  global game
  game = init_game(agent_list)
  game.position = "group leader"
  return jsonify({"status": "reset"})

if __name__ == "__main__":
  socketio.run(app, debug=True, port=5500)