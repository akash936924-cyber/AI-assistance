from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:11434/v1", api_key="ollama")

print("Local AI Assistant Started!")

while True:
    user_input = input("You: ")
    if user_input.lower() == "exit":
        break
    response = client.chat.completions.create(model="gemma3:1b", messages=[{"role": "user", "content": user_input}])
    print("AI:", response.choices[0].message.content)
