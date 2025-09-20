#Project to generate a countdown timer GUI using Tkinter in Python. Where the countdown is 6 months, days, hours, minutes, and seconds also connected via RSS to show title of international news.


import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from datetime import datetime, timedelta
import threading
import feedparser # type: ignore
import webbrowser
import random
import requests

class CountdownTimer:
    def __init__(self, root):
        self.root = root
        self.root.title("6 months Countdown Timer with News and the Gospel")
        self.root.geometry("850x650")
        self.root.configure(bg="#f5f5f5")  # Light grey background

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TLabel', background='#f5f5f5', foreground='#000000', font=('Courier New', 16))
        style.configure('Timer.TLabel', font=('Courier New', 28, 'bold'), foreground='#000000', background='#f5f5f5')
        style.configure('News.TLabel', font=('Courier New', 18, 'bold'), foreground='#000000', background='#f5f5f5')
        style.configure('TButton', background='#f5f5f5', foreground='#000000', font=('Courier New', 14))

        self.label = tk.Label(root, text="", font=('Courier New', 28, 'bold'), bg='#f5f5f5', fg='#000000')
        self.label.pack(pady=30)

        self.end_time = datetime.now() + timedelta(days=180)
        self.update_timer()

        self.news_label = ttk.Label(
            root,
            text="Novice, old habit:",
            style='News.TLabel'
        )
        self.news_label.pack(pady=(10, 5))

        # Refresh Button
        self.refresh_button = ttk.Button(
            root,
            text="Refresh News",
            command=self.manual_refresh_news,
            style='TButton'
        )
        self.refresh_button.pack(pady=(0, 10))

        # Frame for Listbox and Scrollbar
        self.frame = ttk.Frame(root, style='TFrame')
        self.frame.pack(pady=10, padx=20, fill='x')

        self.news_listbox = tk.Listbox(
            self.frame,
            font=('Courier New', 14),
            width=70,
            height=1,  # Will be set dynamically
            cursor="hand2",
            fg='#000000',
            bg='#f5f5f5',
            selectbackground='#000000',
            selectforeground='#f5f5f5',
            borderwidth=0,
            highlightthickness=0
        )
        self.news_listbox.pack(side='left', fill='x', expand=True)
        self.news_listbox.bind("<Double-Button-1>", self.open_selected_link)

        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.news_listbox.yview)
        self.scrollbar.pack(side='right', fill='y')
        self.news_listbox.config(yscrollcommand=self.scrollbar.set)

        self.news_items = []

        self.fetch_news_threaded()

        # Bible verse label (large font, white, wrap, centered)
        self.bible_label = ttk.Label(
            root,
            text="",
            font=('Courier New', 18, 'italic'),
            foreground='#000000',
            background='#f5f5f5',
            wraplength=800,
            justify='center'
        )
        self.bible_label.pack(pady=(20, 10), side='bottom', fill='x')

        self.show_random_bible_quote()

    def update_timer(self):
        now = datetime.now()
        remaining = self.end_time - now

        if remaining.total_seconds() > 0:
            days, seconds = remaining.days, remaining.seconds
            hours = seconds // 3600
            minutes = (seconds % 3600) // 60
            seconds = seconds % 60

            self.label.config(text=f"{days}d {hours}h {minutes}m {seconds}s")
            self.root.after(1000, self.update_timer)
        else:
            self.label.config(text="Time's up!")
            messagebox.showinfo("Countdown Timer", "The countdown has finished!")

    def fetch_news_threaded(self):
        threading.Thread(target=self.fetch_news, daemon=True).start()

    def manual_refresh_news(self):
        # Manual refresh disables button to prevent spamming
        self.refresh_button.config(state='disabled')
        self.fetch_news_threaded()

    def fetch_news(self):
        feeds = [
            ("BBC", "http://feeds.bbci.co.uk/news/world/rss.xml"),
            ("RTV SLO", "https://www.rtvslo.si/rss/slovenija.xml"),
            ("SLO", "https://podcast.rtvslo.si/aktualna_tema.xml"),
            ("SLO_2", "https://www.sta.si/rss/slovenija.xml"),
            ("VEN", "https://www.elnacional.com/feed/"),
            ("VEN_2", "https://www.eluniversal.com/rss/actualidad.xml")
        ]
        news = []
        try:
            for source, url in feeds:
                feed = feedparser.parse(url)
                for entry in feed.entries[:5]:
                    headline = f"[{source}] {entry.title}"
                    link = entry.link
                    news.append((headline, link))
            random.shuffle(news)
            # Only keep up to 10 news items
            news = news[:10]
            self.root.after(0, self.update_news_listbox, news)
            self.root.after(0, self.show_random_bible_quote)
        except Exception as e:
            self.root.after(0, self.update_news_listbox, [(f"Error fetching news: {e}", None)])
        # Re-enable the refresh button after fetching
        self.root.after(0, lambda: self.refresh_button.config(state='normal'))
        # Schedule next auto-refresh in 2 minutes
        self.root.after(120000, self.fetch_news_threaded)

    def update_news_listbox(self, news_items):
        self.news_listbox.delete(0, tk.END)
        self.news_items = news_items
        # Dynamically set the height to the number of news items (max 10)
        self.news_listbox.config(height=len(news_items))
        for idx, (headline, _) in enumerate(news_items, 1):
            self.news_listbox.insert(tk.END, f"{idx}. {headline}")

    def open_selected_link(self, event):
        selection = self.news_listbox.curselection()
        if selection:
            idx = selection[0]
            url = self.news_items[idx][1]
            if url:
                webbrowser.open(url)

    def get_random_bible_verse(self):
        try:
            response = requests.get("https://labs.bible.org/api/?passage=random&type=json")
            if response.status_code == 200:
                data = response.json()[0]
                verse = f"{data['bookname']} {data['chapter']}:{data['verse']} - {data['text']}"
                return verse
            else:
                return "Could not fetch Bible verse."
        except Exception:
            return "Could not fetch Bible verse."

    def show_random_bible_quote(self):
        verse = self.get_random_bible_verse()
        self.bible_label.config(text=verse)

if __name__ == "__main__":
    root = tk.Tk()
    app = CountdownTimer(root)
    root.mainloop()
