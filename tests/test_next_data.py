import json

from ps_price_crawler.next_data import EmbeddedState, extract_embedded_state


def test_extracts_next_data_script():
    html = """
    <html>
      <script id="__NEXT_DATA__" type="application/json">
        {"props":{"pageProps":{"apolloState":{"ROOT_QUERY":{"__typename":"Query"}}}}}
      </script>
    </html>
    """

    state = extract_embedded_state(html)

    assert isinstance(state, EmbeddedState)
    assert state.next_data["props"]["pageProps"]["apolloState"]["ROOT_QUERY"]["__typename"] == "Query"


def test_extracts_env_scripts_by_id():
    env_payload = {
        "args": {"conceptId": "223118"},
        "cache": {"Concept:223118": {"id": "223118", "__typename": "Concept", "name": "Roblox"}},
    }
    html = f"""
    <html>
      <script id="env:abc123" type="application/json">{json.dumps(env_payload)}</script>
    </html>
    """

    state = extract_embedded_state(html)

    assert state.env_scripts["env:abc123"]["args"]["conceptId"] == "223118"
    assert state.env_scripts["env:abc123"]["cache"]["Concept:223118"]["name"] == "Roblox"


def test_missing_next_data_returns_empty_dict():
    state = extract_embedded_state("<html></html>")

    assert state.next_data == {}
    assert state.env_scripts == {}
