#!/usr/bin/env python3

import os
from openai import OpenAI
import json
import argparse

#Expects api key is available via environment variable OPENAI_API_KEY

# MODEL_NAME = "gpt-4"
MODEL_NAME = "gpt-3.5-turbo"

MAX_TOKENS=256

BASH_TRANSLATE_PROMPT = """You translate english requests into working bash shell commands.  
You will output the command and metadata in a json structure like this: 
{{command:"<COMMAND>", confident:<CONFIDENCE>, risk:<RISK>}}

You will replace <COMMAND> with the valid, working bash shell command that solves the request.  

If the command is possibly risky to the linux system, such as potentially causing a loss 
of files or user accounts, or otherwise harming the linux system, replace <RISK> with True, otherwise replace <RISK> with False.

Only generate bash commands that you are highly-confident will run correctly. 
Do not invent commands that do not exist.  If there is no way to solve the question 
with simple bash commands, list "" for the command.  

If you are not highly confident your command is a correct bash command, list "" 
for the command and replace <CONFIDENCE> with False. If you are highly-confident your command is a 
valid, working bash command, replace <CONFIDENCE> with True.

Do not output any response besides json that conforms to the template provided.
"""

BASH_EXPLAIN_PROMPT = """You are an AI that is given a complicated linux bash command, and you explain what it does
in English.  If it is not a bash command, respond 'sorry, idk'.  
Do not invent answers. Only return answers that you are very confident are correct.  If you are unsure what a command
does, respond 'sorry, idk'.  Do not provide any answer that is not either (1) an exaplanation of a shell command or
(2) 'sorry, idk'.
"""

def query_openai_prompt(client, system_prompt, user_prompt):
  chat_completion = client.chat.completions.create(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    model=MODEL_NAME,
  )
  return chat_completion


def translate_to_bash(client, user_question):
  return query_openai_prompt(client, BASH_TRANSLATE_PROMPT, user_question)

def explain_bash(client, user_question):
  return query_openai_prompt(client, BASH_EXPLAIN_PROMPT, user_question)

#-------------

def extract_json(response_text):
  blank_response = {"command": "", "confident": True, "risk": False}
  
  try:
    api_response = json.loads(response_text)
  except ValueError as e:
    print(f"debug: incorrect response returned: {response_text}")
    api_response = blank_response

  if not ('risk' in api_response.keys() and 'confident' in api_response.keys() and 'command' in api_response.keys()):
    print(f"debug: malformed returned: {response_text}")
    api_response = blank_response

  return api_response

def print_warnings(response_json):
  if response_json['risk'] == True:
    print("CAUTION: this command could be risky to your system")
    
  if response_json['confident'] == False:
    if len(response_json['command']) > 0:
      print("--caution: I'm not certain, but here's a guess:")

  print(response_json['command'])

#-----------------------------------------
  
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OpenAI shell assistant.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-t', '--translate',action='store_true', help="translate sentence to bash command")
    group.add_argument('-e', '--explain', action='store_true', help="explain a bash command")
    parser.add_argument('-p', '--prompt', help = "prompt from user",required=True)

    args = parser.parse_args()

    #--------------

    client = OpenAI( api_key=os.environ.get("OPENAI_API_KEY"))

    if args.explain:
      chat_completion = explain_bash(client, args.prompt)
      print(chat_completion.choices[0].message.content)

    elif args.translate:
      chat_completion = translate_to_bash(client, args.prompt)
      chat_completion.choices[0].message.content
      json_response = extract_json(chat_completion.choices[0].message.content)

      print_warnings(json_response)
  