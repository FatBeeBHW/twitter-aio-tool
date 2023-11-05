from collections import deque
from rich.prompt import Prompt
import aiofiles

TOKEN_FILE = "tokens/tokens.txt"
USED_TOKEN_FILE = "tokens/used.txt"
PROXY_FILE = "proxies.txt"

ACTIONS = {
    "1": {"name": "like", "has_message": False},
    "2": {"name": "follow", "has_message": False},
    "3": {"name": "bookmark", "has_message": False},
    "4": {"name": "reply", "has_message": True},
    "5": {"name": "retweet", "has_message": False},
    "6": {"name": "quote", "has_message": True},
    "7": {"name": "view", "has_message": False},
    "8": {"name": "mass_reply", "has_message": False},
    "9": {"name": "mass_quote", "has_message": False},
}


def load_tokens_from_file() -> deque:
    with open(TOKEN_FILE, 'r') as file:
        return deque(line.strip().split(":")[-2:] for line in file)


async def save_used_token(token):
    with open(USED_TOKEN_FILE, 'a') as file:
        file.write(':'.join(token) + '\n')


def load_proxies_from_file() -> deque:
    with open(PROXY_FILE, 'r') as file:
        return deque(line.strip() for line in file)


async def get_action_parameters(action_name):
    # Using action_name to find the corresponding choice number
    choice = [key for key, value in ACTIONS.items() if value["name"]
              == action_name][0]
    action_details = ACTIONS[choice]
    min_delay = int(Prompt.ask(
        "[bold yellow]Minimum Delay[/bold yellow]", default="0"))

    max_delay = int(Prompt.ask(
        "[bold yellow]Maximum Delay[/bold yellow]", default="0"))
    target = Prompt.ask("[bold yellow]Enter the target tweet ID[/bold yellow]")
    message = None
    if action_details["has_message"]:
        message = Prompt.ask("[bold yellow]Enter the message[/bold yellow]")
    total_actions = int(Prompt.ask(
        f"[bold yellow]How many {action_name.replace('_', ' ')}s do you want?[/bold yellow]", default="100"))
    concurrency = int(Prompt.ask(
        f"[bold yellow]Concurrency (how many {action_name.replace('_', ' ')}s at the same time)?[/bold yellow]", default="10"))

    return target, message, total_actions, concurrency, min_delay, max_delay


async def load_from_file(filename):
    async with aiofiles.open(filename, mode='r') as f:
        lines = await f.readlines()
    return [line.strip() for line in lines if line.strip()]


async def save_to_file(filename, data):
    async with aiofiles.open(filename, mode='w') as f:
        await f.write('\n'.join(data))
