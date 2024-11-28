# generative agent utils
# cqz@cs.stanford.edu

# last updated: october 2024

import os
from dotenv import load_dotenv
import numpy as np
import pickle
import pandas as pd
import json
import re
from typing import Dict, List, Tuple

from openai import OpenAI
from anthropic import Anthropic 

# load_dotenv()
# oai = OpenAI(api_key = os.getenv('OPENAI_API_KEY'))
from settings import *
oai = OpenAI(api_key = OPENAI_API_KEY)

ant = Anthropic()
ant.api_key = os.getenv('ANTHROPIC_API_KEY')

def gen_oai(messages, model='gpt-4o', temperature=1):
  if model == None:
    model = 'gpt-4o'
  try:
    response = oai.chat.completions.create(
      model=model,
      temperature=temperature,
      messages=messages,
      max_tokens=1000)
    content = response.choices[0].message.content
    return content
  except Exception as e:
    print(f"Error generating completion: {e}")
    raise e

def simple_gen_oai(prompt, model='gpt-4o', temperature=1):
  messages = [{"role": "user", "content": prompt}]
  return gen_oai(messages, model)

def gen_ant(messages, model='claude-3-5-sonnet-20240620', temperature=1, 
            max_tokens=1000):
  if model == None:
    model = 'claude-3-5-sonnet-20240620'
  try:
    response = ant.messages.create(
      model=model,
      max_tokens=max_tokens,
      temperature=temperature,
      messages=messages
    )
    content = response.content[0].text
    return content
  except Exception as e:
    print(f"Error generating completion: {e}")
    raise e

def simple_gen_ant(prompt, model='claude-3-5-sonnet-20240620'):
  messages = [{"role": "user", "content": prompt}]
  return gen_ant(messages, model)

# Prompt utils

# Prompt inputs
def fill_prompt(prompt, placeholders):
  for placeholder, value in placeholders.items():
    placeholder_tag = f"!<{placeholder.upper()}>!"
    if placeholder_tag in prompt:
      prompt = prompt.replace(placeholder_tag, str(value))
  return prompt

def make_output_format(modules):
  output_format = "Output Format:\n{\n"
  for module in modules:
    if 'name' in module and module['name']:
      output_format += f'    "{module["name"].lower()}": "<your response>",\n'
  output_format = output_format.rstrip(',\n') + "\n}"
  return output_format

def modular_instructions(modules):
    '''
    given some modules in the form

    name (optional, makes it a step)
    instruction (required)

    make the whole prompt
    '''
    prompt = ""
    step_count = 0
    for module in modules:
      if 'name' in module:
        # print(module)
        step_count += 1
        prompt += f"Step {step_count} ({module['name']}): {module['instruction']}\n"
      else:
        prompt += f"{module['instruction']}\n"
    prompt += "\n"
    prompt += make_output_format(modules)
    return prompt

# Prompt outputs
# def parse_json(response, target_keys=None):
#   json_start = response.find('{')
#   json_end = response.rfind('}') + 1
#   cleaned_response = response[json_start:json_end].replace('\\"', '"')
  
#   try:
#     parsed = json.loads(cleaned_response)
#     if target_keys:
#       parsed = {key: parsed.get(key, "") for key in target_keys}
#     return parsed
#   except json.JSONDecodeError:
#     print("Tried to parse json, but it failed. Switching to regex fallback.")
#     print(f"Response: {cleaned_response}")
#     parsed = {}
#     for key_match in re.finditer(r'"(\w+)":\s*', cleaned_response):
#       key = key_match.group(1)
#       if target_keys and key not in target_keys:
#         continue
#       value_start = key_match.end()
#       if cleaned_response[value_start] == '"':
#         value_match = re.search(r'"(.*?)"(?:,|\s*})', 
#                                 cleaned_response[value_start:])
#         if value_match:
#           parsed[key] = value_match.group(1)
#       elif cleaned_response[value_start] == '{':
#         nested_json = re.search(r'(\{.*?\})(?:,|\s*})', 
#                                 cleaned_response[value_start:], re.DOTALL)
#         if nested_json:
#           try:
#             parsed[key] = json.loads(nested_json.group(1))
#           except json.JSONDecodeError:
#             parsed[key] = {}
#       else:
#         value_match = re.search(r'([^,}]+)(?:,|\s*})', 
#                                 cleaned_response[value_start:])
#         if value_match:
#           parsed[key] = value_match.group(1).strip()
    
def parse_json(response, target_keys=None):
    """
    Parses a JSON string response and handles failures with regex fallback.
    Args:
        response (str): The response string containing JSON.
        target_keys (list): List of keys to extract from the JSON if provided.
    Returns:
        dict: Parsed JSON or a fallback dictionary if parsing fails.
    """
    # Locate JSON boundaries
    json_start = response.find('{')
    json_end = response.rfind('}') + 1
    if json_start == -1 or json_end == -1:
        print("No JSON structure found in response.")
        return {}

    # Extract and clean the potential JSON substring
    cleaned_response = response[json_start:json_end].replace('\\"', '"')

    # Attempt to parse JSON directly
    try:
        parsed = json.loads(cleaned_response)
        if target_keys:
            parsed = {key: parsed.get(key, "") for key in target_keys}
        return parsed
    except json.JSONDecodeError:
        print("Failed to parse JSON. Attempting regex fallback.")
        print(f"Original Response: {response}")
        print(f"Extracted JSON-like Segment: {cleaned_response}")

    # Regex fallback for JSON-like structures
    parsed = {}
    try:
        for match in re.finditer(r'"(\w+)":\s*(?:(\{.*?\})|"(.*?)"|([^,}]+))', cleaned_response, re.DOTALL):
            key = match.group(1)
            if target_keys and key not in target_keys:
                continue

            # Determine the value type
            if match.group(2):  # Nested JSON object
                try:
                    parsed[key] = json.loads(match.group(2))
                except json.JSONDecodeError:
                    print(f"Failed to parse nested JSON for key: {key}")
                    parsed[key] = {}
            elif match.group(3):  # String value
                parsed[key] = match.group(3)
            elif match.group(4):  # Other types (e.g., numbers)
                parsed[key] = match.group(4).strip()

    except Exception as e:
        print(f"Regex fallback failed with error: {e}")
    
    return parsed



# end-to-end generation and parsing
def mod_gen(modules: List[Dict], placeholders: Dict, target_keys = None) -> Dict:
  prompt = modular_instructions(modules)
  filled = fill_prompt(prompt, placeholders)
  # print(filled)
  response = simple_gen_oai(filled)
  if len(response) == 0:
    print("Error: response was empty")
    return {}
  if target_keys == None:
    target_keys = [module["name"].lower() for module in modules if "name" in module]
  parsed = parse_json(response, target_keys)
  return parsed

def generate_task_schema(math_problem):
    """
    Generate a detailed task schema for the given math problem using examples for guidance.
    """
    # Example math problem and corresponding schema
    example_problem = """
    Problem: Simplify the fraction \\((m^2 + 2m - 3)/(m - 3)\\).
    """
    
    example_schema = """
    Example Schema:
    {
        "task 1": {
            "description": "Factorize the numerator m^2 + 2m - 3.",
            "steps": [
                "Identify factors of -3 that add to 2.",
                "Rewrite the numerator in its factored form."
            ],
            "variables": {
                "numerator": "m^2 + 2m - 3",
                "factored_form": "(m + 3)(m - 1)"
            }
        },
        "task 2": {
            "description": "Simplify the fraction by canceling common factors.",
            "steps": [
                "Identify the common factor between numerator and denominator.",
                "Cancel the common factor from both numerator and denominator.",
                "Rewrite the simplified fraction."
            ],
            "variables": {
                "denominator": "m - 3",
                "common_factor": "m - 3",
                "simplified_fraction": "(m + 3)"
            }
        },
        "task 3": {
            "description": "State restrictions on the variable.",
            "steps": [
                "Identify values of m that make the denominator zero.",
                "State the restriction: m ≠ 3."
            ],
            "variables": {
                "restricted_value": "m = 3"
            }
        }
    }
    """
    
    # Prompt the LLM with a detailed system message
    system_prompt = f"""
    You are a professional and experienced middle-school math teacher. Decompose the following math problem into a detailed task schema.
    For each task, include:
    - A clear task description.
    - Key steps to solve the task.
    - Important variables or parameters involved.

    MATH PROBLEM:
    {math_problem}

    Below is an example of how to decompose a problem into a task schema:

    {example_problem}

    {example_schema}

    GOAL: Create a detailed task schema for the given math problem.

    ### Guidelines:
    1. Provide the output as a valid JSON object only, with no extra text or commentary.
    2. Do not include explanations or additional formatting like `Schema:` or backticks.

    Return the JSON object only.
    """
    # Generate task schema using the LLM
    response = gen_oai([{"role": "system", "content": system_prompt}])
    task_schema = parse_json(response)
    
    # Handle cases where the response is invalid
    if not task_schema:
        print("Failed to generate a valid task schema. Returning an empty schema.")
        return {}
    
    return task_schema


def identify_potential_mistakes(task_schema):
    """
    Analyze the task schema to identify common mistakes students may make.
    """
    system_prompt = f"""
    You are a math teacher. Analyze the following task schema and identify potential mistakes students may make.
    For each task, describe:
    - Common misunderstandings.
    - Mistakes in using variables or calculations.
    - Missteps in reasoning or problem-solving.

    Task Schema:
    {task_schema}

    Provide the result as a structured JSON object.
    """
    response = gen_oai([{"role": "system", "content": system_prompt}])
    potential_mistakes = parse_json(response)
    if not potential_mistakes:
        print("Failed to identify potential mistakes.")
        return {}
    return potential_mistakes


def create_character_schema(agent, task_schema, potential_mistakes):
    """
    Modify the shared task schema to create a personalized character schema for an agent.
    """
    system_prompt = f"""
    You are a math teacher creating a personalized task schema for a middle school student named {agent.name}.

    {agent.name}'s persona: {agent.persona}

    Based on the potential mistakes identified, modify the task schema to reflect how {agent.name} might approach this problem. Consider their understanding, common misconceptions, and step-by-step thinking process.

    Maintain the overall structure of the given task schema, but customize the details to match {agent.name}'s character.

    Task Schema:
    {json.dumps(task_schema, indent=2)}

    Potential Mistakes:
    {json.dumps(potential_mistakes, indent=2)}

    Example Output:
    {{
        "task 1": {{
            "description": "Factorize the numerator m^2 + 2m - 3.",
            "steps": [
                "Identify factors of -3 that add to 2.",
                "Rewrite the numerator in its factored form."
            ],
            "variables": {{
                "numerator": "m^2 + 2m - 3",
                "factored_form": "(m + 3)(m - 1)"
            }},
            "student_approach": "Hmm, let me see if I can break down the numerator. I know that -3 and 3 add up to 2, so I'll try to rewrite it as (m + 3)(m - 1). Does that look right?"
        }},
        "task 2": {{
            "description": "Simplify the fraction by canceling common factors.",
            "steps": [
                "Identify the common factor between numerator and denominator.",
                "Cancel the common factor from both numerator and denominator.",
                "Rewrite the simplified fraction."
            ],
            "variables": {{
                "denominator": "m - 3",
                "common_factor": "m - 3",
                "simplified_fraction": "(m + 3)"
            }},
            "student_approach": "Okay, let me think about this. The numerator and denominator both have (m - 3), so I can cancel that out. But wait, if m equals 3, then the denominator will be 0. I better be careful with that!"
        }}
    }}
    """
    response = gen_oai([{"role": "system", "content": system_prompt}])
    character_schema = parse_json(response)
    if not character_schema:
        print(f"Failed to create character schema for {agent.name}. Returning the base task schema as fallback.")
        return task_schema  # Return the shared schema as fallback
    return character_schema

