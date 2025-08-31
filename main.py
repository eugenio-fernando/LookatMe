import random

def get_choices():
    player_choice = input("Enter a choice (rock, paper, scissors): ")
    options = ["rock", "paper", "scissors"]
    computer_choice = random.choice(options)
    choices = {"player": player_choice, "computer": computer_choice}
    return choices

def check_winner(player, computer):
    print(f"You chose {player}, computer chose {computer}")
    if player == computer:
        return "It's a tie!"
    elif player == "rock":
        if computer == "scissors":
            return "You win!"
        else:
            return "Paper covers rock, You lose!"
    elif player == "paper":
        if computer == "rock":
            return "You win, paper covers rock!"
        else:
            return "Scissors cut paper, You lose!"
    elif player == "scissors":
        if computer == "paper":
            return "You win, scissors cut paper!"
        else:
            return "Rock crushes scissors, You lose!"

choices = get_choices()
result = check_winner(choices["player"], choices["computer"])
print(result)