from backend import NetworkManager
from gui import MainApp
import customtkinter as ctk


if __name__ == "__main__":
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("green")
    app = MainApp(NetworkManager)

    app.mainloop()
