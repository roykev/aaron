import streamlit as st
import streamlit.components.v1 as components
import base64


def init_player_state():
    if 'player_state' not in st.session_state:
        st.session_state.player_state = {
            'current_time': 0,
            'update_time': False
        }


def st_audio_player(audio_data, audio_format):
    init_player_state()

    b64 = base64.b64encode(audio_data).decode()
    audio_tag = f'<audio id="audio-player" style="width:100%;" controls><source src="data:audio/{audio_format};base64,{b64}" type="audio/{audio_format}"></audio>'

    custom_html = f"""
    <div id="audio-player-container">
        {audio_tag}
        <p>Current Time: <span id="time-display">00:00</span></p>
    </div>
    <script>
        const audioPlayer = document.getElementById('audio-player');
        const timeDisplay = document.getElementById('time-display');

        audioPlayer.ontimeupdate = function() {{
            const minutes = Math.floor(audioPlayer.currentTime / 60);
            const seconds = Math.floor(audioPlayer.currentTime % 60);
            timeDisplay.textContent = minutes.toString().padStart(2, '0') + ':' + seconds.toString().padStart(2, '0');
        }};

        function updatePlayerTime(time) {{
            audioPlayer.currentTime = time;
            audioPlayer.play();
        }}

        // Check for updates
        setInterval(() => {{
            if (window.parent.streamlitSyncWithPlayer_getState) {{
                const state = window.parent.streamlitSyncWithPlayer_getState();
                if (state && state.update_time) {{
                    updatePlayerTime(state.current_time);
                    window.parent.streamlitSyncWithPlayer_resetUpdate();
                }}
            }}
        }}, 100);
    </script>
    """

    components.html(custom_html, height=150)


def jump_to(time):
    st.session_state.player_state['current_time'] = time
    st.session_state.player_state['update_time'] = True


# Expose functions to JavaScript
components.html(
    """
    <script>
    function streamlitSyncWithPlayer_getState() {
        return window.parent.pywebview.state['player_state'];
    }

    function streamlitSyncWithPlayer_resetUpdate() {
        window.parent.pywebview.state['player_state']['update_time'] = false;
    }
    </script>
    """,
    height=0,
)

