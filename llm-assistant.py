#!/usr/bin/env python3

import os
from openai import OpenAI
import json
import argparse

#Expects api key is available via environment variable OPENAI_API_KEY

# DEFAULT_MODEL_NAME = "gpt-4"
DEFAULT_MODEL_NAME = "gpt-3.5-turbo"
DEFAULT_MAX_TOKENS=256

BASH_EXPLAIN_PROMPT = """You are an AI that is given a linux bash command, and 
you explain what it does in English.  If it is not a bash command, respond 
'sorry, idk'.  Do not invent answers. Only return answers that you are very 
confident are correct.  If you are unsure what a command does, respond 
'sorry, idk'.  Do not provide any answer that is not either (1) an explanation 
of a shell command or (2) 'sorry, idk'.
"""

BASH_TRANSLATE_PROMPT = """You receive a task specified by natural language 
that must be accomplished in the linux terminal. You translate that task into 
valid bash shell commands that accomplishes the task.  

Generate a valid bash shell command that will run without errors. 
Do not invent bash commands that do not exist.  

If there is no way to solve the task with bash commands, return
"" for command, True for confident, and False for risky.

If you are not highly confident your command is a valid bash command, return "" 
for command and False for confident. If you are highly-confident your command is 
a valid, working bash command, return True for confident.

If the task is unrelated to linux or bash, return "" for command, True for 
confident, and False for risky.
"""

#-------------------------------------------------------------------------------
#In translate tasks, we will use the function api feature in chat.completions 
#to force chatgpt's output to conform to valid arguments to print_bash_command()

#Must define the signature of the function print_bash_command(). See:
# * https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models
# * https://platform.openai.com/docs/api-reference/chat/create
# * https://json-schema.org/understanding-json-schema/reference/type

FUNCTION_SPECIFICATIONS = [
  {
    "name": "print_bash_command",
    "description": "translate a task in natural language to a valid bash command, with info about riskiness of the command and confidence that the command is valid.",
    "parameters": {
      "type": "object",
      "properties": {
        "command":{
          "type": "string",
          "description": "valid linux bash shell command"
        },
        
        "confident":{
          "type": "boolean",
          "description": "Confidence that translated command is a valid bash shell command: True if the model is confident that command is a valid bash command that solves the task, else False"
        },
        
        "risky":{
          "type": "boolean",
          "description": "Riskiness of the command: True if the bash command is potentially risky to linux systems (e.g. might cause a loss of user accounts or data), else False"
        }
        
      },
      "required": ["command", "confident", "risky"]
    }
  }
]

#-------------------------------------------------------------------------------

def query_openai_prompt(client, system_prompt, user_prompt, model_name, max_tokens):
  """Ask chatgpt questions with text prompt from user"""
  chat_completion = client.chat.completions.create(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    model=model_name,
    max_tokens=max_tokens
  )
  return chat_completion

def query_openai_function_api(client, system_prompt, user_prompt, function_specifications,model_name, max_tokens):
  """Ask chatgpt a prompt whose response must take the form of valid arguments 
  that can be passed to a function. Uses the function api.
  
  See e.g.
  * https://platform.openai.com/docs/api-reference/chat/create
  * https://cookbook.openai.com/examples/how_to_call_functions_with_chat_models
  """
  chat_completion = client.chat.completions.create(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    model=model_name,
    max_tokens=max_tokens,

    functions=function_specifications,
    
    #force chatgpt to create a response conforming to the signature of this function
    #if use 'auto' it can chose between forming arugments or just a textual response (e.g. to ask for clarification)
    function_call={"name": function_specifications[0]['name']}
  )
  return chat_completion

def translate_to_bash(client, user_question, model_name, max_tokens):
  return query_openai_function_api(client, BASH_TRANSLATE_PROMPT, user_question, FUNCTION_SPECIFICATIONS, model_name, max_tokens)

def explain_bash(client, user_question, model_name, max_tokens):
  return query_openai_prompt(client, BASH_EXPLAIN_PROMPT, user_question, model_name, max_tokens)

#-------------

def clean_function_json(response_text):
  """maybe not necessary but verify /clean response in case it is malformed"""

  blank_response = {"command": "", "confident": True, "risky": False}
  
  try:
    api_response = json.loads(response_text)
  except ValueError as e:
    print(f"debug: incorrect response returned: {response_text}")
    api_response = blank_response

  if not ('risky' in api_response.keys() and 'confident' in api_response.keys() and 'command' in api_response.keys()):
    print(f"debug: malformed returned: {response_text}")
    api_response = blank_response

  return api_response

def print_bash_command(command: str, confident: bool, risky: bool):
  """prints a bash command along with the model's confidence and whether or not the command is risky to a linux system"""
  if risky:
    print("CAUTION: this command could be risky to your system")
    
  if not confident:
    if len(command) > 0:
      print("--caution: I'm not certain, but here's a guess:")

  print(command)

#-----------------------------------------
  
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='OpenAI shell assistant.')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-t', '--translate', action='store_true', help="translate sentence to bash command")
    group.add_argument('-e', '--explain', action='store_true', help="explain a bash command")
    parser.add_argument('-p', '--prompt', type=str, help = "prompt from user",required=True)

    parser.add_argument('-m', '--model_name', type=str, default=DEFAULT_MODEL_NAME,
      help = "name of openai model to use, like 'gpt-3.5-turbo' or 'gpt-4'.")
    parser.add_argument('-n', '--max_tokens', type=int, default=DEFAULT_MAX_TOKENS, 
      help = "max tokens", )

    args = parser.parse_args()

    #--------------

    client = OpenAI( api_key=os.environ.get("OPENAI_API_KEY"))

    if args.explain:
      chat_completion = explain_bash(client, args.prompt, args.model_name, args.max_tokens)
      print(chat_completion.choices[0].message.content)

    elif args.translate:
      chat_completion = translate_to_bash(client, args.prompt, args.model_name, args.max_tokens)
      json_response = clean_function_json(chat_completion.choices[0].message.function_call.arguments)

      print_bash_command(**json_response)
  