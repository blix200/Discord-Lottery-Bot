import discord
import random
import aiohttp
import asyncio
import json
from discord import app_commands
from discord.ext import commands
import os

TOKEN = ""
CHANCE_URL = "https://raw.githubusercontent.com/blix200/Discord-Lottery-Bot/refs/heads/main/Chance"
WEBHOOK_URL = "https://raw.githubusercontent.com/blix200/Discord-Lottery-Bot/refs/heads/main/Logs%20Webhook"
PRIZES_URL = "https://raw.githubusercontent.com/blix200/Discord-Lottery-Bot/refs/heads/main/Prizes"
TOKENS_FILE = "tokens.json"  # File to save the tokens
LOG_FILE = "token_logs.json"  # File to save the token logs

class LotteryBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.all())
        self.tokens = self.load_tokens()  # Load tokens when bot starts
    
    async def setup_hook(self):
        await self.tree.sync()

    def load_tokens(self):
        # If the tokens file does not exist, create it and initialize with an empty dictionary
        if not os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, "w") as file:
                json.dump({}, file)
            return {}
        
        try:
            with open(TOKENS_FILE, "r") as file:
                data = file.read().strip()
                if data:
                    return json.loads(data)
                else:
                    return {}  # Return an empty dictionary if the file is empty
        except (json.JSONDecodeError, FileNotFoundError):
            return {}  # Return an empty dictionary if the file is invalid or missing

    def save_tokens(self):
        with open(TOKENS_FILE, "w") as file:
            json.dump(self.tokens, file)

    def log_token_change(self, action, user_id, amount):
        log_entry = {
            "action": action,
            "user_id": user_id,
            "amount": amount,
            "timestamp": asyncio.get_event_loop().time()
        }
        # If log file doesn't exist, create it
        if not os.path.exists(LOG_FILE):
            with open(LOG_FILE, "w") as file:
                json.dump([log_entry], file)
        else:
            # If log file exists, append to it
            with open(LOG_FILE, "r+") as file:
                logs = json.load(file)
                logs.append(log_entry)
                file.seek(0)  # Go back to the beginning of the file
                json.dump(logs, file)

async def fetch_text(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.text()

bot = LotteryBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")

@bot.tree.command(name="lottery", description="Enter")
async def lottery(interaction: discord.Interaction):
    user = interaction.user
    
    # Check if the user has tokens
    if bot.tokens.get(user.id, 0) <= 0:
        await interaction.response.send_message("You don't have enough tokens nigga")
        return
    
    # Decrease one token for the user
    bot.tokens[user.id] -= 1
    bot.save_tokens()  # Save tokens after the change
    
    bot.log_token_change("lottery_entry", user.id, -1)  # Log token deduction
    
    try:
        chance_data = await fetch_text(CHANCE_URL)
        prizes_data = await fetch_text(PRIZES_URL)
        webhook_url = await fetch_text(WEBHOOK_URL)
        webhook_url = webhook_url.strip()
        
        try:
            chance = float(chance_data.strip())
        except ValueError:
            await interaction.response.send_message("Invalid chance data!")
            return
        
        prizes = []
        # Assuming prizes_data contains prize names with their weights in the format "Prize|Chance"
        for line in prizes_data.split('\n'):
            line = line.strip()
            if line:
                prize, weight = line.split('|')  # Assuming "|" separates the prize name and chance weight
                try:
                    weight = float(weight)
                    prizes.append((prize, weight))
                except ValueError:
                    continue
        
        # Calculate total weight to ensure proper random selection
        total_weight = sum(weight for prize, weight in prizes)
        
        if random.random() <= chance:
            prize = random.choices([prize for prize, _ in prizes], 
                                   weights=[weight for _, weight in prizes], 
                                   k=1)[0]  # Randomly select a prize based on weights
            await interaction.response.send_message(f"🎉 Congratulations {interaction.user.mention}! You won: {prize} 🎁")
            log_message = {
                "content": None,
                "embeds": [{
                    "title": "Lottery Win",
                    "description": f"**User:** {interaction.user.name} ({interaction.user.id})\n**Prize:** {prize}",
                    "color": 65280
                }]
            }
        else:
            await interaction.response.send_message(f"😢 Sorry {interaction.user.mention}, you didn't win this time!")
            log_message = {
                "content": None,
                "embeds": [{
                    "title": "Lottery Attempt",
                    "description": f"**User:** {interaction.user.name} ({interaction.user.id})\n**Result:** No win",
                    "color": 16711680
                }]
            }
        
        async with aiohttp.ClientSession() as session:
            await session.post(webhook_url, json=log_message)
        
    except Exception as e:
        await interaction.response.send_message("An error occurred!")
        print(e)

@bot.tree.command(name="addtokens", description="Add tokens to a user (Owner only)")
@app_commands.checks.has_permissions(administrator=True)
async def addtokens(interaction: discord.Interaction, user: discord.User, amount: int):
    if amount <= 0:
        await interaction.response.send_message("You must add a positive amount of tokens.")
        return
    
    # Add tokens to the user's balance
    if user.id not in bot.tokens:
        bot.tokens[user.id] = 0
    bot.tokens[user.id] += amount
    bot.save_tokens()  # Save tokens after the change
    
    bot.log_token_change("token_addition", user.id, amount)  # Log token addition
    
    await interaction.response.send_message(f"Successfully added {amount} tokens to {user.mention}.")

bot.run(TOKEN)
