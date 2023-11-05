import asyncio
from rich import print
from collections import deque
from util.modules import TwitterActions
from rich.prompt import Prompt
from util.util import *
from rich.panel import Panel
from rich.table import Table
import os
import random

# For Windows specifically, due to a known issue with the default event loop
if os.name == 'nt':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

MESSAGES = []
user_lock = asyncio.Lock()
blacklist_lock = asyncio.Lock()  # New lock for managing the blacklist
tokens = load_tokens_from_file()
proxies = load_proxies_from_file()

users = asyncio.Queue()
blacklist = []


async def get_next_proxy():
    proxy = proxies.popleft()
    proxies.append(proxy)
    return proxy


async def initialize_users():
    global blacklist
    async with user_lock:
        if users.qsize() == 0:
            user_list = await load_from_file('mass/users.txt')
            async with blacklist_lock:
                # Load the file directly into the set
                blacklist = set(await load_from_file('mass/blacklist.txt')) if os.path.exists('mass/blacklist.txt') else set()
            for user in user_list:
                if user not in blacklist:
                    await users.put(user)


async def build_mass_message(min_users, max_users):
    original_message = random.choice(MESSAGES)
    user_count = random.randint(min_users, max_users)
    appended_users = []

    for _ in range(user_count):
        async with user_lock:
            if users.empty():
                break
            user = await users.get()
            potential_message = ' '.join(
                [original_message] + ['@' + u for u in appended_users + [user]])
            if len(potential_message) <= 280:
                appended_users.append(user)
                async with blacklist_lock:
                    blacklist.add(user)
            else:
                await users.put(user)

    async with user_lock:
        for user in appended_users:  # Remove the appended users from the queue
            if not users.empty() and user in users._queue:
                users._queue.remove(user)
        remaining_users = list(users._queue)
        await save_to_file('mass/users.txt', remaining_users)

    async with blacklist_lock:
        await save_to_file('mass/blacklist.txt', blacklist)
    print(' '.join([original_message] + ['@' + u for u in appended_users]))
    return ' '.join([original_message] + ['@' + u for u in appended_users])


class TokenWorker:

    def __init__(self, ct0, auth, proxy, action, target, message=None):
        self.ct0 = ct0
        self.auth = auth
        self.proxy = proxy
        self.action = action
        self.target = target
        self.message = message

    async def run(self, min_delay, max_delay):

        async with TwitterActions(self.ct0, self.auth, self.proxy) as twitter_action:
            rand_sleep = random.randint(
                int(min_delay), int(max_delay))
            if rand_sleep != 0:
                print(
                    f"[green][*][white] {rand_sleep} [green]seconds to the next action.")
                await asyncio.sleep(rand_sleep)
            status_code, screen_name = await twitter_action.validate_account()
            # print(status_code)
            if not screen_name:
                return

            if self.action == "like":
                await twitter_action.like(self.target, screen_name)
            elif self.action == "reply":
                await twitter_action.reply(self.target, screen_name, self.message)
            elif self.action == "quote":
                await twitter_action.quote(self.target, screen_name, self.message)
            elif self.action == "follow":
                await twitter_action.follow(self.target, screen_name)
            elif self.action == "bookmark":
                await twitter_action.bookmark(self.target, screen_name)
            elif self.action == "retweet":
                await twitter_action.retweet(self.target, screen_name)
            elif self.action == "views":
                await twitter_action.views(self.target, screen_name)


class TokenManager:
    def __init__(self, action, target, total_actions, message=None, concurrency=None):
        self.action = action
        self.target = target
        self.message = message
        self.concurrency = concurrency or 1  # Default concurrency if not provided
        self.total_actions = total_actions

    @classmethod
    async def create(cls, action, target, total_actions, message=None, concurrency=None):
        instance = cls(action, target, total_actions, message,
                       concurrency)
        return instance

    async def manage_tokens(self, min_users=None, max_users=None, min_delay=0, max_delay=0):
        remaining_actions = self.total_actions
        if len(tokens) < remaining_actions:
            print(
                "[bold red][!] Not enough tokens for the requested number of actions!")
            return

        # Define the semaphore
        semaphore = asyncio.Semaphore(self.concurrency)

        async def worker_wrapper(token):
            async with semaphore:
                ct0, auth = token  # Splitting the token
                proxy = await get_next_proxy()
                await save_used_token(token)  # Save the full token

                # Determine the action type and potentially generate a unique message
                if self.action == "mass_reply":
                    message = await build_mass_message(min_users, max_users)
                    action = "reply"  # Use the standard reply action
                elif self.action == "mass_quote":
                    message = await build_mass_message(min_users, max_users)
                    action = "quote"  # Use the standard quote action
                else:
                    message = self.message
                    action = self.action

                worker = TokenWorker(
                    ct0, auth, proxy, action, self.target, message)
                await worker.run(min_delay, max_delay)

        # List to gather all the worker tasks
        tasks = []
        while tokens and remaining_actions > 0:
            token = tokens.popleft()
            tasks.append(worker_wrapper(token))
            remaining_actions -= 1

        # Wait for all tasks to complete
        await asyncio.gather(*tasks)


def display_main_menu(token_count: int, proxies_count: int):
    os.system('cls' if os.name == 'nt' else 'clear')
    from rich.console import Console
    console = Console()

    menu = Table(show_header=False, header_style="blink2",
                 border_style="royal_blue1", padding=(0, 3))
    menu.add_column(justify="right", style="dim", width=3)
    menu.add_column(justify="left")

    menu.add_row(
        "", f"[bold royal_blue1]🚀 Tokens: {token_count} | 🌐 Proxies: {proxies_count}")
    menu.add_row(
        "", f"[bold royal_blue1]🚀 Users: {users.qsize()} | 🌐 Blacklisted: {len(blacklist)}")

    menu.add_row("", "")
    menu.add_row("", "[bold royal_blue1]🛸 Simple Actions")
    menu.add_row("[1]", "👍 Like")
    menu.add_row("[2]", "🤝 Follow")
    menu.add_row("[3]", "🤝 Bookmark")
    menu.add_row("[4]", "💬 Reply")
    menu.add_row("[5]", "🔁 Retweet")
    menu.add_row("[6]", "📌 Quote")
    menu.add_row("[7]", "👀 Views")
    menu.add_row("", "")
    menu.add_row("", "[bold royal_blue1]🌌 Mass Actions")
    menu.add_row("[8]", "💬 Mass Reply")
    menu.add_row("[9]", "📌 Mass Quote")
    menu.add_row("", "")
    menu.add_row("", "")
    menu.add_row(
        "→", ":speech_balloon: [cyan]Official Telegram: [link=https://t.me/twitterfunhouse]@twitterfunhouse[/link]")
    menu.add_row(
        "→", ":lollipop: [gold1]Github: [link=https://github.com/FatBeeBHW]https://github.com/FatBeeBHW[/link]")
    menu.add_row("", "")

    menu.add_row(
        "→", "[gold1][link=https://t.me/beeproxies]BeeProxies | $3.00/GB at @beeproxies[/link]")
    menu.add_row(
        "→", "[blue][link=https://t.me/twittercrack]xCloud - @twittercrack[/link]")

    panel = Panel(menu, title="[bold cyan3]🌌 [link=https://t.me/twitterfunhouse]xAIO Menu[/link] | [link=https://t.me/FatBeeBHW]@fatbeebhw[/link] 🌌",
                  border_style="blink2", expand=False)
    console.print(panel)


async def handle_choice(choice):
    if choice not in ACTIONS:
        if choice == "x":
            print("[bold red]Exiting...[/bold red]")
            return "exit"
        return

    action_details = ACTIONS[choice]
    action_name = action_details["name"]

    if action_name in ["mass_reply", "mass_quote"]:
        min_users = int(Prompt.ask(
            "[bold yellow]Minimum Tags[/bold yellow]", default="0"))
        max_users = int(Prompt.ask(
            "[bold yellow]Maximum Tags[/bold yellow]", default="0"))

    if action_details["has_message"]:
        target, message, total_actions, concurrency, min_delay, max_delay = await get_action_parameters(action_name)
    else:
        target, _, total_actions, concurrency, min_delay, max_delay = await get_action_parameters(action_name)

    manager = await TokenManager.create(action_name, target, total_actions, message if "message" in locals() else None, concurrency)

    if action_name in ["mass_reply", "mass_quote"]:
        await manager.manage_tokens(min_users, max_users, min_delay, max_delay)
    else:
        await manager.manage_tokens(None, None, min_delay, max_delay)


async def main_loop():
    while True:
        global MESSAGES
        MESSAGES = await load_from_file('mass/messages.txt')
        await initialize_users()
        token_count = len(tokens)
        proxies_count = len(proxies)
        display_main_menu(token_count, proxies_count)

        choice = Prompt.ask("[bold chartreuse3]Choose an option", choices=[
                            "1", "2", "3", "4", "5", "6", "7", "8", "9", "x"], default="x", show_choices=False)

        result = await handle_choice(choice)
        if result == "exit":
            break

        Prompt.ask(
            "[bold chartreuse3]All Tasks are completed. Press Any Button to return.")

# Running the main loop
asyncio.run(main_loop())
