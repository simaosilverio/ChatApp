import socket
import threading
import json
import time
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
        'filename': 'server.log',
        'formatter': 'default',
    }},
    'root': {
        'handlers': ['console', 'file'],
        'level': 'DEBUG',
    },
})


class User:
    def __init__(self, username, connection):
        self.username = username  # Username of the user
        self.connection = connection  # Socket connection for the user
        self.messages = []  # Empty list to store messages for this user

    def add_message(self, message):
        self.messages.append(message)

    def get_messages(self):
        return self.messages


class Message:
    def __init__(self, sender, receiver, content):
        self.sender = sender  # Sender of the message
        self.receiver = receiver  # Receiver of the message
        self.content = content  # Content of the message
        self.timestamp = time.time()  # The time when the message was created


class Command:
    def __init__(self, command_type, data):
        self.command_type = command_type  # Type of command
        self.data = data  # Data associated with the command


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


class ChatAppServer:
    def __init__(self, host, port):
        self.host = host  # Host IP address
        self.port = port  # Port number
        self.server_socket = socket.socket(
            socket.AF_INET, socket.SOCK_STREAM)  # Create a server socket
        self.clients = {}  # Empty dictionary to store connected clients
        self.lock = threading.Lock()  # Lock for thread-safe operations

    def start(self):
        try:
            # Starts the server
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logging.info(f"Server listening on {self.host}:{self.port}.")
        except socket.error as e:
            logging.error(f"Error binding server socket: {e}.")
            # Try to bind to a different port if the default port is in use
            for port in range(self.port + 1, self.port + 11):
                try:
                    self.server_socket.bind((self.host, port))
                    self.server_socket.listen(5)
                    logging.info(f"Server listening on {self.host}:{port}.")
                    self.port = port
                    break
                except socket.error as e:
                    logging.error(
                        f"Error binding server socket on port {port}: {e}.")
            else:
                logging.critical("Could not bind server to any port.")
                return

        while True:
            try:
                client_socket, client_address = self.server_socket.accept()
                logging.info(f"New connection from {client_address}.")
                # When new connection accepted, new thread is started to handle the client
                client_thread = threading.Thread(
                    target=self.handle_client, args=(client_socket,))
                client_thread.start()
            except Exception as e:
                logging.error(f"Error accepting connection: {e}.")

    def handle_client(self, client_socket):
        try:
            username = client_socket.recv(1024).decode('utf-8')
            user = User(username, client_socket)
            # Adds user to clients dictionary in a thread-safe manner
            with self.lock:
                self.clients[username] = user
            logging.info(f"{username} connected.")

            # Receive and process commands from the client
            while True:
                try:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        break

                    command = Parser.parse(data)
                    if command:
                        self.process_command(user, command)
                except Exception as e:
                    logging.error(f"Error handling client: {e}.")
                    break

            logging.info(f"{username} disconnected.")
            with self.lock:
                del self.clients[username]
            client_socket.close()

            self.broadcast_user_list()

        except Exception as e:
            logging.error(f"Error in handle client: {e}.")

    # Process received commands from the client
    def process_command(self, user, command):
        try:
            if command.command_type == 'SEND':
                self.handle_send_command(user, command)
            elif command.command_type == 'USERLIST':
                self.broadcast_user_list()
            elif command.command_type == 'HISTORY':
                self.handle_history_command(user)
            elif command.command_type == 'SEARCH':
                self.handle_search_command(user, command)
        except Exception as e:
            logging.error(
                f"Error processing command {command.command_type}: {e}.")

    # Handles the 'SEND' command
    def handle_send_command(self, user, command):
        args = command.data
        if len(args) == 2:
            receiver, content = args
            # Check if receiver exists
            if receiver in self.clients:
                # Creates 'Message' object
                message = Message(user.username, receiver, content)
                # Adds to the receiver's messages
                self.clients[receiver].add_message(message)
                logging.info(
                    f"Message from {user.username} to {receiver}: {content}")
                # Sends message to the receiver
                response = Parser.format("SEND", user.username, content)
                self.clients[receiver].connection.send(
                    response.encode('utf-8'))

    # Handles the 'HISTORY' command
    def handle_history_command(self, user):
        message_history = user.get_messages()
        response_messages = [
            f"{msg.sender}: {msg.content}" for msg in message_history]
        response = Parser.format("HISTORY", *response_messages)
        user.connection.send(response.encode('utf-8'))

    # Handles the 'SEARCH' command
    def handle_search_command(self, user, command):
        search_query = command.data[0]
        found_messages = []
        # Search through all messages for the query and sends back any found messages
        for client in self.clients.values():
            for message in client.get_messages():
                if search_query in message.content:
                    found_messages.append(
                        {'sender': message.sender, 'content': message.content})
        response = Parser.format("SEARCH", json.dumps(
            {'found_messages': found_messages}))
        user.connection.send(response.encode('utf-8'))

    # Handles the 'USERLIST' command; broadcast the user list to all connected clients
    def broadcast_user_list(self):
        user_list = list(self.clients.keys())
        response = Parser.format("USERLIST", "; ".join(user_list))
        with self.lock:
            for user in self.clients.values():
                user.connection.send(response.encode('utf-8'))


if __name__ == "__main__":
    try:
        server = ChatAppServer('localhost', 8888)
        server.start()
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}.")
