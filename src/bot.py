import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

UUID_REGEX = re.compile(
    r"^[0-9a-fA-F]{32}$|^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


@dataclass(frozen=True)
class ServerTarget:
    name: str
    address: str


@dataclass
class BotConfig:
    token: str
    servers: list[ServerTarget]
    request_timeout_seconds: int = 10
    max_concurrency: int = 8


def load_config(path: str) -> BotConfig:
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Arquivo de configuracao nao encontrado: {path}. "
            "Copie config.example.json para config.json e ajuste as informacoes."
        )
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    servers_raw = raw.get("servers", [])
    servers = [
        ServerTarget(name=entry["name"], address=entry["address"])
        for entry in servers_raw
        if isinstance(entry, dict) and entry.get("name") and entry.get("address")
    ]
    token = raw.get("discord_token")
    if not token:
        raise ValueError("Campo 'discord_token' ausente no config.json.")
    max_concurrency = raw.get("max_concurrency", 8)
    if not isinstance(max_concurrency, int) or max_concurrency < 1:
        max_concurrency = 1
    return BotConfig(
        token=token,
        servers=servers,
        request_timeout_seconds=raw.get("request_timeout_seconds", 10),
        max_concurrency=max_concurrency,
    )


def normalize_uuid(value: str) -> str:
    return value.replace("-", "").lower()


async def fetch_json(session: aiohttp.ClientSession, url: str) -> dict[str, Any]:
    async with session.get(url) as response:
        response.raise_for_status()
        return await response.json()


async def fetch_uuid_for_name(
    session: aiohttp.ClientSession, name: str
) -> Optional[str]:
    url = f"https://api.mojang.com/users/profiles/minecraft/{name}"
    async with session.get(url) as response:
        if response.status == 204:
            return None
        response.raise_for_status()
        data = await response.json()
    return data.get("id")


async def fetch_server_status(
    session: aiohttp.ClientSession, address: str
) -> dict[str, Any]:
    url = f"https://api.mcsrvstat.us/2/{address}"
    return await fetch_json(session, url)


def extract_players(payload: dict[str, Any]) -> tuple[list[str], list[str]]:
    players = payload.get("players", {})
    names = []
    for entry in players.get("list") or []:
        if isinstance(entry, dict):
            name = entry.get("name")
            if name:
                names.append(name)
        elif isinstance(entry, str):
            names.append(entry)
    uuids = []
    for entry in players.get("uuid", []) or []:
        if isinstance(entry, dict):
            raw_uuid = entry.get("uuid") or ""
            if raw_uuid:
                uuids.append(raw_uuid)
        elif isinstance(entry, str):
            uuids.append(entry)
    return names, uuids


async def find_player_servers(
    session: aiohttp.ClientSession,
    targets: list[ServerTarget],
    player_name: str,
    player_uuid: Optional[str],
    max_concurrency: int,
) -> list[ServerTarget]:
    matches: list[ServerTarget] = []
    semaphore = asyncio.Semaphore(max_concurrency)

    async def check_server(target: ServerTarget) -> None:
        async with semaphore:
            try:
                payload = await fetch_server_status(session, target.address)
            except (aiohttp.ClientError, asyncio.TimeoutError):
                return
            if not payload.get("online"):
                return
            names, uuids = extract_players(payload)
            if player_name.lower() in {name.lower() for name in names}:
                matches.append(target)
                return
            if player_uuid:
                normalized = normalize_uuid(player_uuid)
                if normalized in {normalize_uuid(uuid) for uuid in uuids}:
                    matches.append(target)

    await asyncio.gather(*(check_server(target) for target in targets))
    return matches


class CristianMinecraftBot(commands.Bot):
    def __init__(self, config: BotConfig) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.http_timeout = aiohttp.ClientTimeout(total=config.request_timeout_seconds)
        self.http_session: Optional[aiohttp.ClientSession] = None
        self.logger = logging.getLogger("cristian-minecraft-bot")

    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession(timeout=self.http_timeout)
        await self.tree.sync()

    async def close(self) -> None:
        if self.http_session:
            await self.http_session.close()
        await super().close()


config = load_config(os.getenv("CONFIG_PATH", "config.json"))

bot = CristianMinecraftBot(config)


@bot.event
async def on_ready() -> None:
    bot.logger.info("Bot conectado como %s (ID: %s)", bot.user, bot.user.id)


@bot.tree.command(
    name="procurar",
    description="Procura em quais servidores cristãos um jogador está online.",
)
@app_commands.describe(
    jogador="Nome Minecraft ou UUID para localizar nos servidores configurados."
)
async def procurar(interaction: discord.Interaction, jogador: str) -> None:
    if bot.http_session is None:
        await interaction.response.send_message(
            "Sessão HTTP não inicializada. Tente novamente.", ephemeral=True
        )
        return

    if not bot.config.servers:
        await interaction.response.send_message(
            "Nenhum servidor configurado ainda. Atualize o config.json.",
            ephemeral=True,
        )
        return

    await interaction.response.defer(thinking=True)

    player_name = jogador
    player_uuid = None

    if UUID_REGEX.match(jogador):
        player_uuid = jogador
    else:
        player_uuid = await fetch_uuid_for_name(bot.http_session, jogador)
        if player_uuid is None:
            await interaction.followup.send(
                f"Jogador `{jogador}` não encontrado na Mojang.",
                ephemeral=True,
            )
            return

    matches = await find_player_servers(
        bot.http_session,
        bot.config.servers,
        player_name=player_name,
        player_uuid=player_uuid,
        max_concurrency=bot.config.max_concurrency,
    )

    if not matches:
        await interaction.followup.send(
            "Nenhum servidor cristão configurado indicou esse jogador online.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="Jogador encontrado",
        description="Encontrei o jogador nos servidores abaixo:",
        color=discord.Color.green(),
    )
    for server in matches:
        embed.add_field(
            name=server.name,
            value=f"Endereço: `{server.address}`",
            inline=False,
        )
    await interaction.followup.send(embed=embed)


@bot.tree.command(
    name="servidores",
    description="Lista os servidores cristãos configurados.",
)
async def servidores(interaction: discord.Interaction) -> None:
    if not bot.config.servers:
        await interaction.response.send_message(
            "Nenhum servidor configurado ainda. Atualize o config.json.",
            ephemeral=True,
        )
        return
    embed = discord.Embed(
        title="Servidores configurados",
        color=discord.Color.blue(),
    )
    for server in bot.config.servers:
        embed.add_field(
            name=server.name,
            value=f"Endereço: `{server.address}`",
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot.run(config.token)
