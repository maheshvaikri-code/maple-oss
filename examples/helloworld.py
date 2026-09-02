from maple import Agent, Message, Priority, Config

# Create and configure an agent
config = Config(
    agent_id="my_agent",
    broker_url="localhost:8080"
)
agent = Agent(config)

# Define message handler
@agent.handler("GREETING")
def handle_greeting(message):
    print(f"Received: {message.payload['text']}")
    return Message(
        message_type="GREETING_RESPONSE",
        payload={"text": "Hello back!"}
    )

# Start the agent
agent.start()

# Send a message
message = Message(
    message_type="GREETING",
    receiver="another_agent",
    priority=Priority.HIGH,
    payload={"text": "Hello, MAPLE!"}
)

result = agent.send(message)
if result.is_ok():
    print("Message sent successfully!")