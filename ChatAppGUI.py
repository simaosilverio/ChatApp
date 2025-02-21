import tkinter as tk
from tkinter import messagebox, simpledialog
import socket
import json
import threading
import logging
import logging.config

# Configure logging
logging.config.dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(process)d %(thread)d %(levelname)s - %(message)s',
    }},
    'handlers': {'console': {
        'class': 'logging.StreamHandler',
        'formatter': 'default',
    }, 'file': {
        'class': 'logging.FileHandler',
        'filename': 'gui.log',
        'formatter': 'default',
    }},
    'root': {
        'handlers': ['console', 'file'],
        'level': 'DEBUG',
    },
})


class Command:
    def __init__(self, command_type, data):
        self.command_type = command_type    # Store the type of command
        self.data = data    # Store the associated data with the command


class Parser:
    @staticmethod
    def format(command_type, *args):
        # Formats command type and arguments into a string separated by '|'
        return f"{command_type}|{'|'.join(map(str, args))}"

    @staticmethod
    def parse(data):
        # Split the string by '|' to extract command type and arguments
        try:
            parsed_data = data.split('|')
            command_type = parsed_data[0]
            args = parsed_data[1:]
            return Command(command_type, args)
        except Exception as e:
            logging.error(f"Error parsing data: {e}.")
            return None


class ChatAppGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("ChatApp")

        # Variables to store server address and username
        self.server_address = tk.StringVar()
        self.username = tk.StringVar()

        self.connected = False  # Connection status
        self.client_socket = None  # Client socket

        self.setup_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)  # Close window

    def setup_widgets(self):
        # Chat history display
        self.chat_history_text = tk.Text(
            self.root, width=50, height=10, state='disabled')
        self.chat_history_text.grid(
            row=0, column=0, columnspan=4, padx=5, pady=5)

        # Entry for typing messages
        self.message_entry = tk.Entry(self.root, width=50)
        self.message_entry.grid(row=1, column=0, columnspan=3, padx=5, pady=5)

        # Button to send messages
        self.send_button = tk.Button(
            self.root, text="Send", command=self.send_message)
        self.send_button.grid(row=1, column=3, padx=5, pady=5)

        # Button to connect to server
        self.connect_button = tk.Button(
            self.root, text="Connect", command=self.connect_to_server)
        self.connect_button.grid(row=2, column=0, padx=5, pady=5)

        # Button to retrieve message history
        self.history_button = tk.Button(
            self.root, text="History", command=self.message_history)
        self.history_button.grid(row=2, column=1, padx=5, pady=5)

        # Button to refresh user list
        self.users_button = tk.Button(
            self.root, text="Users", command=self.refresh_user_list)
        self.users_button.grid(row=2, column=2, padx=5, pady=5)

        # Entry and button to search messages
        self.find_entry = tk.Entry(self.root, width=50)
        self.find_entry.grid(row=3, column=0, columnspan=3, padx=5, pady=5)
        self.find_button = tk.Button(
            self.root, text="Find", command=self.search_message)
        self.find_button.grid(row=3, column=3, padx=5, pady=5)

        # Listbox to display users
        self.user_listbox = tk.Listbox(self.root)
        self.user_listbox.grid(row=0, column=4, rowspan=4, padx=5, pady=5)

        # Button to exit the application
        self.exit_button = tk.Button(
            self.root, text="Exit", command=self.exit_app)
        self.exit_button.grid(row=0, column=4, sticky="ne", padx=5, pady=5)

    def connect_to_server(self):
        if not self.connected:
            # Ask for server address and username
            server_address = simpledialog.askstring(
                "Server Address", "Enter Server Address:", parent=self.root)
            if not server_address:
                return

            username = simpledialog.askstring(
                "Username", "Enter Username:", parent=self.root)
            if not username:
                return

            try:
                # Send username to the server
                self.client_socket = socket.socket(
                    socket.AF_INET, socket.SOCK_STREAM)
                self.client_socket.connect((server_address, 8888))
                self.client_socket.send(username.encode('utf-8'))

                # Update connection status and variables
                self.connected = True
                self.server_address.set(server_address)
                self.username.set(username)

                messagebox.showinfo("Info", "Connected to server.")
                self.send_command("USERLIST")

                # Start thread to receive messages
                threading.Thread(target=self.receive_messages).start()

            except Exception as e:
                logging.error(f"Failed to connect to server: {e}.")
                messagebox.showerror(
                    "Error", f"Failed to connect to server: {e}.")
        else:
            messagebox.showerror("Error", "Already connected to the server.")

    def receive_messages(self):
        while self.connected:
            try:
                # Receives data from the server and decodes it
                data = self.client_socket.recv(1024).decode('utf-8')
                if not data:
                    break

                # Parses the data into a 'Command' object
                command = Parser.parse(data)

                # Handle the command
                if command:
                    self.process_server_command(command)
            except Exception as e:
                logging.error(f"Error receiving data: {e}.")
                break

    # Process received commands from the server
    def process_server_command(self, command):
        if command.command_type == "SEND":
            sender, message = command.data
            self.chat_window_update(f"{sender}: {message}\n")
        elif command.command_type == "USERLIST":
            user_list = command.data[0].split("; ")
            self.update_user_list(user_list)
        elif command.command_type == "HISTORY":
            self.chat_window_update("Message History:\n")
            for message in command.data:
                self.chat_window_update(f"{message}\n")
        elif command.command_type == "SEARCH":
            search_result = json.loads(command.data[0])['found_messages']
            self.display_search_result(search_result)

    # Update the user list
    def update_user_list(self, user_list):
        # Clear the existing user list and add the new user list
        self.user_listbox.delete(0, tk.END)
        self.chat_window_update("Connected Users:\n")
        for user in user_list:
            self.user_listbox.insert(tk.END, user)
            self.chat_window_update(f"{user}\n")

    # Display search result
    def display_search_result(self, search_result):
        if search_result:
            message = search_result[0]
            sender = message['sender']
            content = message['content']
            self.chat_window_update(f"Search Result:\n{sender}: {content}\n")
        else:
            messagebox.showinfo("Search Result", "No matching message found.")

    # Send a message to the selected user
    def send_message(self):
        if self.connected:
            click = self.user_listbox.curselection()
            if click:
                selected_user = self.user_listbox.get(click)
                current_user = self.username.get()
                if selected_user != current_user:
                    message = self.message_entry.get()
                    if message:
                        self.send_command("SEND", selected_user, message)
                        self.message_entry.delete(0, tk.END)
                    else:
                        messagebox.showerror("Error", "Enter a message.")
                else:
                    messagebox.showerror(
                        "Error", "Cannot send message to yourself.")
            else:
                messagebox.showerror("Error", "Select a user.")
        else:
            messagebox.showerror("Error", "Connect to the server.")

    # Refresh the list of users
    def refresh_user_list(self):
        if self.connected:
            self.send_command("USERLIST")
        else:
            messagebox.showerror("Error", "Connect to the server.")

    # Retrieve message history
    def message_history(self):
        if self.connected:
            self.send_command("HISTORY")
        else:
            messagebox.showerror("Error", "Connect to the server.")

    # Search for a message
    def search_message(self):
        if self.connected:
            search_query = self.find_entry.get()
            self.send_command("SEARCH", search_query)
        else:
            messagebox.showerror("Error", "Connect to the server.")

    # Send a command to the server
    def send_command(self, command_type, *args):
        command = Parser.format(command_type, *args)
        try:
            self.client_socket.send(command.encode('utf-8'))
        except Exception as e:
            logging.error(f"Error sending command: {e}.")

    # Exit the application
    def exit_app(self):
        if self.connected:
            try:
                self.client_socket.close()
            except Exception as e:
                logging.error(f"Failed to close socket: {e}.")
                messagebox.showerror("Error", f"Failed to close socket: {e}.")
        self.root.quit()

    # Update the chat window
    def chat_window_update(self, message):
        self.chat_history_text.configure(state='normal')
        self.chat_history_text.insert(tk.END, message)
        self.chat_history_text.configure(state='disabled')


def main():
    root = tk.Tk()
    app = ChatAppGUI(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}.")
