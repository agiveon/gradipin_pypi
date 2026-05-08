# Gradipin

**Static URLs for your Gradio demos. One line of code.**

Gradio's `share=True` gives you a public URL that changes every time you restart
your demo. Gradipin sits in front of those tunnels and gives you a stable
`https://gradipin.com/go/<your-app>` link that always points to whichever
tunnel is currently live — perfect for tweets, READMEs, and your team's "demos"
channel.

```python
import gradio as gr
import gradipin

demo = gr.Interface(lambda x: x.upper(), "text", "text")
gradipin.share(demo, app="vision-model")
# → https://gradipin.com/go/vision-model
```

That's it. Restart the script, get a new tunnel, your friends still hit the
same URL.

## Install

```bash
pip install gradipin[gradio]
```

If you're not using Gradio (e.g. you have your own ngrok / cloudflared tunnel
in front of a FastAPI app), the base install is enough:

```bash
pip install gradipin
```

## Authenticate

Grab an API key from [gradipin.com/dashboard](https://gradipin.com/dashboard),
then either:

```bash
gradipin login           # saves to ~/.gradipin/config
```

or set the environment variable:

```bash
export GRADIPIN_KEY=gp_live_...
```

or pass it explicitly:

```python
gradipin.share(demo, app="vision-model", key="gp_live_...")
```

## Lower-level API

Have your own public URL? Use the context manager:

```python
import gradipin

with gradipin.session("my-api", url="https://abc.ngrok.io"):
    run_my_fastapi_server()
```

## CLI

```bash
gradipin login            # save your API key
gradipin logout           # forget your API key
gradipin list             # list your apps and their status
gradipin status <app>     # check whether a specific app is live
```

## Configuration precedence

API key resolution (first match wins):

1. Explicit `key=...` argument
2. `GRADIPIN_KEY` environment variable
3. `~/.gradipin/config` (written by `gradipin login`)
4. `GRADIPIN_KEY` in a `.env` file in the current working directory

Other environment variables:

- `GRADIPIN_API_URL` — override the API base URL (default
  `https://api.gradipin.com/v1`). Useful for self-hosted backends or local
  development.
- `GRADIPIN_HEARTBEAT` — heartbeat interval in seconds (default `30`).

## Development

```bash
git clone https://github.com/gradipin/gradipin-python
cd gradipin-python
uv sync --extra dev --extra gradio
uv run pytest
```

## License

MIT
