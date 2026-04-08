token = input("Paste new token: ")
with open("/Users/swaggzbagz/trading-bot-squad/.env", "r") as f:
    content = f.read()
content = "\n".join([f"NEXUS_TELEGRAM_TOKEN={token}" if "NEXUS_TELEGRAM_TOKEN" in line else line for line in content.split("\n")])
with open("/Users/swaggzbagz/trading-bot-squad/.env", "w") as f:
    f.write(content)
print("Done!")
