import pygame
import os
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))

from constants import SCREEN_W, SCREEN_H, FPS
from game import Game

def main():
    pygame.init()
    pygame.display.set_caption("StarMiner")
    try:
        icon = pygame.image.load("assets/2D/icon.png")
        pygame.display.set_icon(icon)
    except Exception:
        pass
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    game = Game(screen)
    game.run()

if __name__ == "__main__":
    main()
