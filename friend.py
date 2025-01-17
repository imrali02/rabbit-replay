class Friend:
    def __init__(self, name, client_socket):
        self.name = name
        self.socket = client_socket

    def send_message(self, message):
        try:
            self.socket.sendall(message.encode())
            print(f"Message sent to {self.name}: {message}")
        except Exception as e:
            print(f"Error sending message to {self.name}: {e}")

    def recv_message(self):
        try:
            data = self.socket.recv(1024).decode()
            print(f"Message received from {self.name}: {data}")
            return data
        except Exception as e:
            print(f"Error receiving message from {self.name}: {e}")
            return None

    def close_connection(self):
        try:
            self.socket.close()
            print(f"Connection with {self.name} closed.")
        except Exception as e:
            print(f"Error closing connection with {self.name}: {e}")

    async def keep_alive(self, client_list):
        self.send_message("are you still alive?")
        response = self.recv_message()
        if response == None or response == "":
            print(
                f"friend {self.name} is unresponsive. summarily executing {self.name}"
            )
            client_list.remove(self)
        else:
            print(f"friend {self.name} ack success.")

    def __repr__(self):
        return f"{self.name} at {self.socket}"
