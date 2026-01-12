import socket, threading, sys

nickname = input("Choose your nickname: ")
ip = input("Input ip address: ") or "127.0.0.1"

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # socket initialization
client.connect((ip, 8888))  # connecting client to server


def receive():
    while True:  # making valid connection
        try:
            message = client.recv(1024).decode('ascii')
            if message == 'NICKNAME':
                client.send(nickname.encode('ascii'))
            else:
                print(message)
        except:  # case on wrong ip/port details
            print("An error occurred!")
            client.close()
            break


def write():
    while True:
        user_input = input('')
        if user_input.lower() == 'quit':
            sys.exit()
        
        print("\033[F\033[K", end="")

        message = f"{nickname}: {user_input}"
        client.send(message.encode('ascii'))



receive_thread = threading.Thread(target=receive)  # receiving multiple messages
receive_thread.start()
write_thread = threading.Thread(target=write)  # sending messages
write_thread.start()