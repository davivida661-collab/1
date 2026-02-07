# 🤖 Bot Discord para localizar jogadores em servidores cristãos de Minecraft

Este projeto entrega um bot Discord completo que busca jogadores de Minecraft por **nome** ou **UUID** e informa em quais servidores cristãos configurados eles estão online.

## ✨ Funcionalidades

- 🔎 Pesquisa por **nome** ou **UUID** do Minecraft.
- 📋 Lista servidores cristãos configurados.
- ⚡ Consulta rápida usando a API pública do `mcsrvstat.us`.
- 🔐 Configuração simples via arquivo `config.json`.
- 🧵 Controle de concorrência para evitar bloqueios em muitas consultas.
- 🔗 Geração do link de convite via `/convite` (com `client_id` configurado).

## ✅ Pré-requisitos

- Python 3.10+
- Token de bot Discord (portal de desenvolvedores da Discord)

## 🚀 Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## ⚙️ Configuração

1. Copie o arquivo de exemplo:

```bash
cp config.example.json config.json
```

2. Preencha o `config.json` com:

- Seu **token** do bot Discord.
- Lista de servidores cristãos que deseja monitorar.

Exemplo:

```json
{
  "discord_token": "COLE_SEU_TOKEN_AQUI",
  "request_timeout_seconds": 10,
  "max_concurrency": 8,
  "client_id": "123456789012345678",
  "servers": [
    {
      "name": "Servidor Cristão Exemplo",
      "address": "play.exemplo.com"
    }
  ]
}
```

## ▶️ Como executar

```bash
python src/bot.py
```

## 🧩 Comandos Discord

- `/procurar jogador:<nome_ou_uuid>` → Procura o jogador nos servidores cristãos configurados.
- `/servidores` → Lista os servidores configurados.
- `/convite` → Exibe o link de convite do bot (precisa do `client_id`).

## 📝 Observações importantes

- A busca por jogadores depende do **status público** do servidor. Alguns servidores podem ocultar listas de jogadores.
- Não existe API oficial que revele em qual servidor um jogador está; o bot varre apenas os servidores configurados.
- Caso o servidor esteja offline ou bloqueie listas de jogadores, ele será ignorado na resposta.

## 🔗 Link de convite do bot

Para obter o link automaticamente, defina o `client_id` no `config.json` e use o comando `/convite`.
Se preferir gerar manualmente, substitua o `CLIENT_ID` abaixo:

```
https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=0&scope=bot%20applications.commands
```

## 📄 Licença

Este projeto é open-source. Use, modifique e compartilhe à vontade.
