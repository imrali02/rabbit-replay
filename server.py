import socket
import time
import select
import asyncio
from friend import Friend
import os

client_list = []  # client list is global var now
goon_users = set()


def trigger_buzzer(name):
    for friend in client_list:
        if friend.name == name:
            friend.send_message("trigger alarm")
            if friend.recv_message() == "signal ack":
                return f"successfully activated {friend.name}'s signal"
            else:
                return "something went wrong. they probably arent plugged in!"


def trigger_buzzers_for_all_devices():
    global client_list
    names = []
    signals_recvd = "received by: "
    for friend in client_list:
        friend.socket.settimeout(1)
        friend.send_message("trigger alarm")
        ack = friend.recv_message()
        if ack == "signal ack":
            names.append(friend.name)

    signals_recvd = signals_recvd + ", ".join(names)
    return signals_recvd

    # principally violates DRY but O(n) instead of O(n^2) my beloved


def start_server(ip, port):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setblocking(False)
    server_sock.bind((ip, port))
    server_sock.listen()
    print(f"Server started at {ip}:{port}")
    return server_sock


def handshake(client_socket):
    try:
        client_socket.settimeout(5)
        data = client_socket.recv(1024).decode()

        if data in ["kurapikaisnow", "drowningin", "indescribableemptiness"]:
            # this connection is from the bot, it will deliver a command and then disconnect.
            process_command(client_socket, data)
            return False, None
        else:
            client_socket.sendall(b"hello")
            print("Handshake successful!")
            return True, Friend(data, client_socket)

    except socket.timeout:
        print("Handshake timeout.")
    except Exception as e:
        print(f"Error during handshake: {e}")
    return False, None


def process_command(client_socket, data):

    if data == "kurapikaisnow":
        result = trigger_buzzers_for_all_devices()
        client_socket.sendall(result.encode())
        # clients will now close their connections. don't close the connection here because that puts server in TIME_WAIT and blocks new commands for 2xMSL seconds

    elif data == "drowningin":
        client_socket.sendall(b"present target")
        target = client_socket.recv(1024).decode()
        result = trigger_buzzer(target)
        client_socket.sendall(result.encode())

    else:
        client_socket.sendall(get_client_string().encode())


async def manage_clients(server_sock, client_list):
    while True:
        ready_to_read, _, _ = select.select([server_sock], [], [], 0)
        if ready_to_read:
            try:
                client_socket, client_address = server_sock.accept()
                print(f"New connection from {client_address}")

                success, to_add = handshake(client_socket)

                if success:
                    client_list.append(to_add)
                else:
                    client_socket.close()
            except Exception as e:
                print(f"Error accepting connection: {e}")

        await asyncio.sleep(3)
        os.system("clear")
        print_client_list()
        # prints all connected clients, not important if you can't/don't want to see terminal output


async def prune_client_list(client_list):
    while True:

        tasks = [friend.keep_alive(client_list) for friend in client_list]
        await asyncio.gather(*tasks)

        await asyncio.sleep(4)


def print_client_list():
    global client_list
    # os.system("clear")
    print("current friend list\n")
    for friend in client_list:
        print(friend)
    print("\n\n\n\n\n")


def get_client_string():
    global client_list
    return "Clients: " + ", ".join(friend.name for friend in client_list)


async def run_server(ip, port):
    global client_list
    server_sock = start_server(ip, port)

    manage_task = asyncio.create_task(manage_clients(server_sock, client_list))
    prune_task = asyncio.create_task(prune_client_list(client_list))

    await asyncio.gather(manage_task, prune_task)


async def main():
    await run_server("192.168.1.48", 42069)


asyncio.run(main())
