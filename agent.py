#!/usr/bin/env python
"""
Simple LLM agent for Task 1.
Takes a question as command-line argument and returns JSON response.
"""

import json
import sys
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv('.env.agent.secret')

def main():
    print("Starting agent...", file=sys.stderr)
    
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No question provided"}), file=sys.stdout)
        sys.exit(1)
    
    question = sys.argv[1]
    print(f"Question: {question}", file=sys.stderr)
    
    api_key = os.getenv('LLM_API_KEY')
    api_base = os.getenv('LLM_API_BASE')
    model = os.getenv('LLM_MODEL', 'qwen3-coder-plus')
    
    if not api_key:
        print(json.dumps({"error": "LLM_API_KEY not set in .env.agent.secret"}), file=sys.stdout)
        sys.exit(1)
    
    if not api_base:
        print(json.dumps({"error": "LLM_API_BASE not set in .env.agent.secret"}), file=sys.stdout)
        sys.exit(1)
    
    print(f"Using model: {model}", file=sys.stderr)
    print(f"API Base: {api_base}", file=sys.stderr)
    
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=api_base
        )
        
        print("Calling LLM...", file=sys.stderr)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Answer questions concisely."},
                {"role": "user", "content": question}
            ],
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        print(f"Got response ({len(answer)} chars)", file=sys.stderr)
        
        result = {
            "answer": answer,
            "tool_calls": []
        }
        
        print(json.dumps(result, ensure_ascii=False), file=sys.stdout)
        
    except Exception as e:
        error_msg = f"Error calling LLM: {str(e)}"
        print(error_msg, file=sys.stderr)
        print(json.dumps({"error": error_msg}), file=sys.stdout)
        sys.exit(1)

if __name__ == "__main__":
    main()
