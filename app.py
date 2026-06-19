import os
import subprocess
import sys 
import streamlit as st

# --- 1. PAGE SETUP AND STATE MANAGEMENT ---
st.set_page_config(page_title="YouTube Video Downloader", page_icon="🚀🚀", layout="centered")
st.title("🚀 Flexible YouTube Video Downloader 🚀")
st.write("Easily download YouTube videos in various formats and qualities.\nJust paste the URL and choose your preferred option!")

# Track state so the download button doesn't vanish on click
if 'last_url' not in st.session_state:
    st.session_state.last_url = ""
if 'file_paths' not in st.session_state:
    st.session_state.file_paths = []

# -- 2. AUTO-UPDATE FUNCTION FOR yt-dlp ---
@st.cache_resource # This ensures the update check runs only once per session, preventing unnecessary updates on every interaction.
def auto_update_yt_dlp():
    """
    Silently updates yt-dlp to the latest version once per session.
    """
    st.write("Checking for yt-dlp updates...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade","--quiet", "yt-dlp"], 
            check=True
            )
        st.write("yt-dlp has been updated to the latest version.")
    except Exception as e: #subprocess.CalledProcessError
        st.write(f"Failed to update yt-dlp, continuing with the current version. Error: {e}")

# RUN THE AUTO UPDATE FUNCTION FIRST
auto_update_yt_dlp()

# --- 3. UI DASHBOARD ---
url = st.text_input("Enter YouTube Video URL:", value=st.session_state.last_url)

# Clears old downloads if the user pastes a new URL, ensuring the interface remains clean and relevant to the current download.
if url and url != st.session_state.last_url:
    st.session_state.last_url = url
    st.session_state.file_paths = []  # Clear previous file path when URL changes

# Replace the old terminal inputs with Streamlit widgets for a more interactive experience
format_label = st.radio(
    "Choose a download format:",
    options=[
        "1. Best Quality (Video + Audio, MP4)",
        "2. Audio Only (MP3)",
        "3. Good Quality (Max 720p, MP4)",
        "4. Smallest File Size (Lowest Quality, MP4)"
    ]
)

is_playlist = st.checkbox("Is this URL a playlist?", value=False)

# Map the selected format to the corresponding choice value
choice_mapping = {
    "1. Best Quality (Video + Audio, MP4)": "1",
    "2. Audio Only (MP3)": "2",
    "3. Good Quality (Max 720p, MP4)": "3",
    "4. Smallest File Size (Lowest Quality, MP4)": "4"
}
user_choice = choice_mapping[format_label]

# --- 4. CORE DOWNLOAD LOGIC --- 
# 2. IMPORT yt-dlp AFTER THE UPDATE
import yt_dlp

def download_youtube_video(url, choice, is_playlist=False, download_path='downloads'):
    """
    Downloads a YouTube video using varying yt-dlp options based on user choice.

    Downloads Video [YouTube] from a given URL to the specified path.
    
    Args:
        url (str): The URL of the Video.
        choice (str): The quality/format choice.
        is_playlist (bool): Whether the URL should be treated as a playlist.
        download_path (str): The directory to save the video (defaults to current directory).
    """
    cookie_path = os.path.join(os.path.dirname(__file__), 'cookies.txt')
    # Create the download directory if it doesn't exist
    if not os.path.exists(download_path):
        os.makedirs(download_path)

    # Configuration options for yt-dlp
    # Base options that apply to all downloads
    ydl_opts = {
        'noplaylist': not is_playlist,
        'quiet': True,
        'sleep_interval_requests': 2, # Adds a delay between requests to be polite to the server
        'source_address': '0.0.0.0', # Binds to all available network interfaces
        'cookiesfile': cookie_path, # Path to cookies file for authenticated downloads
        'extractor_args': {'youtube': ['player_client=ios,web_safari']},
        'sleep_interval': 8,        # Wait AT LEAST 8 seconds between video downloads
        'max_sleep_interval': 25,   # Wait UP TO 25 seconds (Randomly picks a number between 8 and 25)
        #'limit_rate': '4M',         # Limits download speed to 3 Megabytes per second
        'max_downloads': 20,          # Limit the number of videos to download from a playlist
    }

    if is_playlist:
        ydl_opts['noplaylist'] = False  # Allow playlist downloads
        # Create a folder for the playlist using the playlist title
        ydl_opts['outtmpl'] = f"{download_path}/%(playlist_title)s/%(playlist_index)s-%(title)s.%(ext)s"
    else:
        ydl_opts['noplaylist'] = True  # Ensure playlist downloads are disabled
        ydl_opts['outtmpl'] = f"{download_path}/%(title)s.%(ext)s"

    # Format Selection    
    # 1. Best Quality (Video + Audio)
    if choice == '1':
        ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        ydl_opts['merge_output_format'] = 'mp4'

    # 2. Audio Only (MP3)
    elif choice == '2':
        ydl_opts['format'] = 'bestaudio/best'
        # Post-processors tell yt-dlp to extract the audio and convert it to mp3 using FFmpeg
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
        
    # 3. Maximum 720p Quality
    elif choice == '3':
        # Selects the best video that is 720p or lower, plus the best audio
        ydl_opts['format'] = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best'
        ydl_opts['merge_output_format'] = 'mp4'
        
    # 4. Smallest File Size (Lowest Quality)
    elif choice == '4':
        ydl_opts['format'] = 'worstvideo[ext=mp4]+worstaudio[ext=m4a]/worst[ext=mp4]/worst'
        ydl_opts['merge_output_format'] = 'mp4'
        
    downloaded_files = []  # Clear cache if the user switches to a completely new URL

    # Execute the download
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # extract_info with download=True downloads the file and returns its metadata, including the final file path.
            info = ydl.extract_info(url, download=True)

        # Helper function to get correct path for single videos and playlists
        def get_final_path(video_info):
            file_path = ydl.prepare_filename(video_info)
            # If we converted to mp3, yt-dlp renames the file extension on disk
            if choice == '2':
                file_path = os.path.splitext(file_path)[0] + '.mp3'
            return file_path
        
        # Aggregates file paths
        # Handles Playlists (multiple videos) and Single Videos
        if 'entries' in info:  # Playlist case
            for entry in info['entries']:
                if entry: # Check if the entry is not None (sometimes entries can be None if there was an error with that video)
                    final_path = get_final_path(entry)
                    downloaded_files.append(final_path)

        else:  # Single video case
            final_path = get_final_path(info)
            downloaded_files.append(final_path)

        return downloaded_files  # Return the list of downloaded file paths
        
    except Exception as e:
         st.error(f"An error occurred during download: {e}")
         return []
    
# --- 5. EXECUTION and PRESENTATION ---
if st.button("Download"):
    if not url:
        st.warning("Please enter a YouTube video URL before clicking Download.")
    else:
        with st.spinner("Processing your request...\nthis may take a minute depending on the file size and internet connection."):
            files = download_youtube_video(url, user_choice, is_playlist=is_playlist, download_path="downloads")
            if files:
                st.session_state.file_paths = files  # Store the downloaded file paths in session state
                st.success(f"Download completed successfully! {len(files)} file(s) downloaded.")

# PRESENT FILES TO USER
if st.session_state.file_paths:
    st.write("###")
    st.subheader("💾 Ready to Save")
    for file_path in st.session_state.file_paths:
        if os.path.exists(file_path):
            file_name = os.path.basename(file_path)
            with open(file_path, "rb") as f:
                st.download_button(
                    label=f"Download {file_name}",
                    data=f,
                    file_name=file_name,
                    mime="audio/mpeg" if file_path.endswith('.mp3') else "video/mp4"
                )


#"C:\Users\HomePC\Documents\Python\PythonProjects"):
#https://youtu.be/t_jGAK0LRRk

# COMMENT GRAVEYARD:
# The --quiet flag suppresses the output of the installation process, making it less verbose.
# check_call over run. It will raise an exception if the command fails, which we can catch to handle errors gracefully.

# Clear cache if the user switches to a completely new URL
# if url != st.session_state.last_url:
#     st.session_state.last_url = url
#     st.session_state.file_path = None  # Clear previous file path when URL changes

#'listformats': True, # This will print a table of all available files
# --- THE FIX: Pass cookies from your browser ---
# The comma at the end inside the parenthesis is REQUIRED.
#'cookiesfrombrowser': ('chrome',),

# Prevent downloading playlists by default (useful if passing a video URL that is part of a playlist)
        # Ensure the final merged file is an mp4
        #'merge_output_format': 'mp4',

# quiet to False : Suppresses a lot of the console noise, leaving only warnings/errors
#'no_warnings': False,
        #'subtitleslangs': ['Eng']
# # Sets the output filename format to "Title.extension"
        # 'outtmpl': '%(title)s.%(ext)s',

#print(f"Playlist mode enabled. Files will be saved to: {download_path}/%(playlist_title)s/")

# 'best' downloads the best single file (video+audio).
# 'bestvideo+bestaudio/best' downloads the best video and best audio separately and merges them (requires ffmpeg).

# else:
#     print("Invalid choice. Defaulting to Best Quality.")
#     ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
#     ydl_opts['merge_output_format'] = 'mp4'

# except yt_dlp.utils.DownloadError as de:
#     print(f"\nFailed to download the video. Error: {de}")
# except Exception as e:
#     print(f"\nAn unexpected error occurred: {e}")

#print(f"Extracting data and downloading Video from: {url}...")
        # # Initialize the YoutubeDL class with our options           
        # with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        #     #The download method takes a list of URLs
        #     ydl.download([url])
        # print("\nDownload completed successfully!")
