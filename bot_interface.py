# for imran: these fns are how the bot interfaces with the server. this is all the bot needs and they should
# work out of the box with just ip/port combos.
# you should populate the discord msg event handler with these functions whenever a command is needed.
import socket


def send_command_all(ip, port):
    try:

        client_socket = connect_to_server(ip, port)
        client_socket.sendall(b"kurapikaisnow")
        response = client_socket.recv(1024).decode()
        client_socket.close()
        print(response)
        return response
    except Exception as e:
        print(f"Error during command delivery: {e}")
        return False


# target string should be the name of the user that was provided by their goon signal.
# THIS IS **NOT** THEIR CURRENT DISCORD NAME. is it possible to make the discord bot send the actual
# username and not server nickname? the goonsignal provided name is going to be hardcoded and won't change.
def send_command_single(ip, port, target):
    try:
        client_socket = connect_to_server(ip, port)
        client_socket.sendall(b"drowningin")
        response = client_socket.recv(1024).decode()
        if response == "present target":
            client_socket.sendall(target.encode())
            response = client_socket.recv(1024).decode()
            client_socket.close()
            return response
        return False

    except Exception as e:
        print(f"Error during command delivery: {e}")
        return False


# retrieves a comma separated list of all connected signals. useful if youre wondering if it went off or not. why am i adding new features at this hour? i am sick. this is sickness. i do love sockets though.
def send_command_list(ip, port):
    try:
        client_socket = connect_to_server(ip, port)
        client_socket.sendall(b"indescribableemptiness")
        response = client_socket.recv(1024).decode()
        client_socket.close()
        if response == "":
            return "request failed"
        else:
            return response
    except Exception as e:
        return "request failed"


# needed for the fns, irrelevant to you
def connect_to_server(ip, port):
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        client_socket.connect((ip, port))
        print(f"Connected to server at {ip}:{port}")
        return client_socket
    except Exception as e:
        print(f"Connection failed: {e}")
        return None
