#!/usr/bin/env python3

import curses
import random
import time
import subprocess
import signal
import sys
import os

SNAKE_CHAR = '██'
APPLE_CHAR = '🍏'
SPECIAL_APPLE_CHAR = '🍎'
OBSTACLE_CHAR = '💣'
SEGMENT_WIDTH = 2
SOUND_CMD = ['paplay', '/usr/share/sounds/freedesktop/stereo/bell.oga']
LEADERBOARD_FILE = "leaderboard.txt"
MAX_NAME_LEN = 12
MAX_LEADERBOARD_ENTRIES = 5

DIRECTIONS = {
    'up': (-1, 0),
    'down': (1, 0),
    'left': (0, -SEGMENT_WIDTH),
    'right': (0, SEGMENT_WIDTH),
}

KEY_DIRECTION_MAP = {
    curses.KEY_UP: 'up',
    curses.KEY_DOWN: 'down',
    curses.KEY_LEFT: 'left',
    curses.KEY_RIGHT: 'right',
    ord('w'): 'up',
    ord('s'): 'down',
    ord('a'): 'left',
    ord('d'): 'right',
}

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    for i in range(1, 8):
        curses.init_pair(i, i, -1)
    curses.init_pair(10, curses.COLOR_GREEN, -1)  # snake color default
    curses.init_pair(30, curses.COLOR_RED, -1)    # obstacle color default

def random_color(exclude=[]):
    choices = [i for i in range(1, 8) if i not in exclude]
    return random.choice(choices)

def play_sound():
    subprocess.Popen(SOUND_CMD, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def random_empty_position(sh, sw, snake, apples, obstacles):
    min_y, max_y = 1, sh - 2
    max_x = sw - SEGMENT_WIDTH - 1
    possible_x = [x for x in range(SEGMENT_WIDTH, max_x, SEGMENT_WIDTH)]
    while True:
        y = random.randint(min_y, max_y)
        x = random.choice(possible_x)
        pos = [y, x]
        if pos not in snake and pos not in apples and pos not in obstacles:
            return pos

def initialize_snake(sh, sw, direction, length=3):
    mid_y = sh // 2
    mid_x = (sw // 2 // SEGMENT_WIDTH) * SEGMENT_WIDTH
    dy, dx = DIRECTIONS[direction]

    snake = []
    for i in range(length):
        y = mid_y - dy * i
        x = mid_x - dx * i
        y = max(1, min(sh - 2, y))
        x = max(SEGMENT_WIDTH, min(sw - SEGMENT_WIDTH * 2, x))
        snake.append([y, x])
    return snake

def draw_figlet_text(stdscr, text_lines, start_y, start_x, color_pair):
    for i, line in enumerate(text_lines):
        stdscr.attron(curses.color_pair(color_pair))
        stdscr.addstr(start_y + i, start_x, line)
        stdscr.attroff(curses.color_pair(color_pair))

def load_leaderboard():
    if not os.path.exists(LEADERBOARD_FILE):
        return []
    entries = []
    with open(LEADERBOARD_FILE, "r") as f:
        for line in f:
            parts = line.rstrip("\n").split('\t')
            if len(parts) == 3 and parts[1].isdigit() and parts[2].isdigit():
                entries.append((parts[0], int(parts[1]), int(parts[2])))
    entries.sort(key=lambda x: (-x[1], x[2]))
    return entries[:MAX_LEADERBOARD_ENTRIES]

def save_leaderboard(entries):
    with open(LEADERBOARD_FILE, "w") as f:
        for name, score, elapsed in entries[:MAX_LEADERBOARD_ENTRIES]:
            f.write(f"{name}\t{score}\t{elapsed}\n")

def add_score_to_leaderboard(name, score, elapsed):
    entries = load_leaderboard()
    entries.append((name, score, elapsed))
    entries.sort(key=lambda x: (-x[1], x[2]))
    entries = entries[:MAX_LEADERBOARD_ENTRIES]
    save_leaderboard(entries)

def clear_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        os.remove(LEADERBOARD_FILE)

def ask_name(stdscr):
    stdscr.clear()
    stdscr.refresh()
    curses.echo()
    curses.curs_set(1)
    stdscr.nodelay(False)

    sh, sw = stdscr.getmaxyx()
    prompt = f"New High Score! Enter your name (max {MAX_NAME_LEN} chars): "
    stdscr.addstr(sh // 2, max(0, sw // 2 - len(prompt) // 2), prompt)
    stdscr.refresh()

    win_y = sh // 2 + 1
    win_x = max(0, sw // 2 - MAX_NAME_LEN // 2)
    win = curses.newwin(1, MAX_NAME_LEN + 1, win_y, win_x)
    win.keypad(True)
    win.refresh()

    box = ''
    while True:
        ch = win.getch()
        if ch in (curses.KEY_ENTER, 10, 13):
            break
        elif ch in (27,):
            box = "Anonymous"
            break
        elif ch in (curses.KEY_BACKSPACE, 127, 8):
            if len(box) > 0:
                box = box[:-1]
                win.clear()
                win.addstr(0, 0, box)
                win.refresh()
        elif 32 <= ch <= 126 and len(box) < MAX_NAME_LEN:
            box += chr(ch)
            win.addstr(0, len(box) - 1, chr(ch))
            win.refresh()

    curses.noecho()
    curses.curs_set(0)
    stdscr.clear()
    stdscr.refresh()
    return box.strip() if box.strip() else "Anonymous"

def draw_leaderboard(stdscr, start_y, sw):
    entries = load_leaderboard()
    if not entries:
        return
    stdscr.attron(curses.A_BOLD)
    stdscr.addstr(start_y, sw // 2 - 12, "LEADERBOARD (Score | Time)")
    stdscr.attroff(curses.A_BOLD)
    for i, (name, score, elapsed) in enumerate(entries):
        mins = elapsed // 60
        secs = elapsed % 60
        time_str = f"{mins:02d}:{secs:02d}"
        line = f"{i+1}. {name[:MAX_NAME_LEN]:<{MAX_NAME_LEN}} {score:>3}  {time_str}"
        stdscr.addstr(start_y + i + 1, sw // 2 - len(line)//2, line)

def title_screen(stdscr, sound_on):
    sh, sw = stdscr.getmaxyx()
    init_colors()

    figlet_proc = subprocess.run(['figlet', '-f', 'standard', 'pysnake'], capture_output=True, text=True)
    figlet_lines = figlet_proc.stdout.splitlines()

    figlet_height = len(figlet_lines)
    figlet_width = max(len(line) for line in figlet_lines)
    start_y = max(0, sh // 2 - figlet_height // 2 - 8)
    start_x = max(0, sw // 2 - figlet_width // 2)

    title_color = random_color(exclude=[7])
    snake_color = random_color(exclude=[7])
    curses.init_pair(15, snake_color, -1)

    demo_direction = 'right'
    demo_dir_vec = DIRECTIONS[demo_direction]
    demo_snake = initialize_snake(sh, sw, demo_direction, length=5)

    demo_obstacles = []

    def make_demo_apple(snake_and_apples_and_obstacles):
        pos = random_empty_position(sh, sw, snake_and_apples_and_obstacles, [], demo_obstacles)
        color = random_color()
        return [pos[0], pos[1], color]

    demo_apples = []
    for _ in range(10):
        demo_apples.append(make_demo_apple(demo_snake + demo_apples))

    while len(demo_obstacles) < 4:
        pos = random_empty_position(sh, sw, demo_snake + [a[:2] for a in demo_apples], [], demo_obstacles)
        demo_obstacles.append(pos)

    stdscr.nodelay(True)

    while True:
        key = stdscr.getch()
        if key in (ord('q'), 27):
            sys.exit(0)
        elif key == ord('o'):
            sound_on = not sound_on
        elif key == ord('c'):
            clear_leaderboard()
        elif key != -1:
            break

        head = [demo_snake[0][0] + demo_dir_vec[0], demo_snake[0][1] + demo_dir_vec[1]]

        if random.random() < 0.2:
            demo_direction = random.choice(list(DIRECTIONS.keys()))
            demo_dir_vec = DIRECTIONS[demo_direction]
            head = [demo_snake[0][0] + demo_dir_vec[0], demo_snake[0][1] + demo_dir_vec[1]]

        collision = (
            head in demo_snake or
            head[0] <= 0 or head[0] >= sh - 1 or
            head[1] <= 0 or head[1] > sw - SEGMENT_WIDTH - 1 or
            head in demo_obstacles
        )
        if collision:
            demo_dir_vec = (-demo_dir_vec[0], -demo_dir_vec[1])
            head = [demo_snake[0][0] + demo_dir_vec[0], demo_snake[0][1] + demo_dir_vec[1]]

        demo_snake.insert(0, head)

        ate_apple_idx = next((i for i, a in enumerate(demo_apples) if a[0] == head[0] and a[1] == head[1]), None)
        if ate_apple_idx is not None:
            demo_apples[ate_apple_idx] = make_demo_apple(demo_snake + demo_apples)
        else:
            demo_snake.pop()

        stdscr.erase()
        stdscr.attron(curses.color_pair(15))
        stdscr.border()
        stdscr.attroff(curses.color_pair(15))

        for apple in demo_apples:
            y, x, color = apple
            curses.init_pair(20 + color, color, -1)
            stdscr.attron(curses.color_pair(20 + color))
            stdscr.addstr(y, x, APPLE_CHAR)
            stdscr.attroff(curses.color_pair(20 + color))

        stdscr.attron(curses.color_pair(30))
        for y, x in demo_obstacles:
            stdscr.addstr(y, x, OBSTACLE_CHAR)
        stdscr.attroff(curses.color_pair(30))

        stdscr.attron(curses.color_pair(15))
        for y, x in demo_snake:
            stdscr.addstr(y, x, SNAKE_CHAR)
        stdscr.attroff(curses.color_pair(15))

        draw_figlet_text(stdscr, figlet_lines, start_y, start_x, title_color)

        start_msg = "Press any key to start"
        quit_msg = "Press Q to exit"
        clear_msg = "Press C to clear leaderboard"
        sound_msg = f"Sound: {'ON' if sound_on else 'OFF'} (Press O to toggle)"
        controls_msg = "Use arrow keys or WASD to move — Hold key to move faster"

        stdscr.attron(curses.color_pair(title_color) | curses.A_BOLD)
        stdscr.addstr(start_y + figlet_height + 1, sw // 2 - len(start_msg) // 2, start_msg)
        stdscr.addstr(start_y + figlet_height + 2, sw // 2 - len(quit_msg) // 2, quit_msg)
        stdscr.addstr(start_y + figlet_height + 3, sw // 2 - len(clear_msg) // 2, clear_msg)
        stdscr.attroff(curses.color_pair(title_color) | curses.A_BOLD)

        stdscr.attron(curses.color_pair(7))
        stdscr.addstr(start_y + figlet_height + 5, sw // 2 - len(controls_msg) // 2, controls_msg)
        stdscr.addstr(start_y + figlet_height + 6, sw // 2 - len(sound_msg) // 2, sound_msg)
        stdscr.attroff(curses.color_pair(7))

        draw_leaderboard(stdscr, start_y + figlet_height + 8, sw)

        stdscr.refresh()
        time.sleep(0.15)

    return sound_on

SPECIAL_APPLE_CHAR = '🍎'
SPECIAL_APPLE_COLOR = curses.COLOR_YELLOW  # special apple color

def run_game(stdscr, sound_on_initial=True):
    sh, sw = stdscr.getmaxyx()
    if sw < 20 or sh < 10:
        stdscr.clear()
        stdscr.addstr(0, 0, "Terminal too small for this game.")
        stdscr.refresh()
        time.sleep(3)
        return 0, 0, True, False

    init_colors()
    snake_color = random_color(exclude=[7])
    curses.init_pair(10, snake_color, -1)
    apple_color = random_color(exclude=[snake_color])

    curses.curs_set(0)
    stdscr.nodelay(True)

    base_delay = 0.2
    min_delay = 0.032

    direction = random.choice(list(DIRECTIONS.keys()))
    dir_vec = DIRECTIONS[direction]

    snake = initialize_snake(sh, sw, direction)

    score = 0
    start_time = time.time()
    sound_on = sound_on_initial
    paused = False

    last_move_time = time.time()
    last_draw_time = time.time()
    timer_refresh_interval = 1 / 60
    speed_boost = False

    apples = []
    obstacles = []

    grow_segments = 0  # <--- Initialize grow_segments here

    def get_apple_count(score):
        if score >= 51:
            return 6
        elif score >= 41:
            return 5
        elif score >= 31:
            return 4
        elif 21 <= score <= 30:
            return 3
        elif 11 <= score <= 20:
            return 2
        elif 1 <= score <= 10:
            return 1
        else:
            return 1

    def get_obstacle_count(score):
        if score < 15:
            return 0
        elif 15 <= score < 25:
            return 3
        else:
            return 6

    def spawn_apples_and_obstacles():
        apple_count = get_apple_count(score)
        obstacle_count = get_obstacle_count(score)

        # Remove excess normal apples (not special)
        normal_apples = [a for a in apples if not a.get('special', False)]
        while len(normal_apples) > apple_count:
            for i in range(len(apples) - 1, -1, -1):
                if not apples[i].get('special', False):
                    apples.pop(i)
                    break
            normal_apples = [a for a in apples if not a.get('special', False)]

        # Add normal apples to meet count
        while len(normal_apples) < apple_count:
            pos = random_empty_position(sh, sw, snake, [a['pos'] for a in apples], obstacles)
            color = random_color()
            apples.append({'pos': pos, 'color': color})
            normal_apples = [a for a in apples if not a.get('special', False)]

        # Spawn special apple every 21 points if none present
        special_exists = any(a.get('special', False) for a in apples)
        if score != 0 and score % 21 == 0 and not special_exists:
            pos = random_empty_position(sh, sw, snake, [a['pos'] for a in apples], obstacles)
            apples.append({'pos': pos, 'color': SPECIAL_APPLE_COLOR, 'special': True})

        while len(obstacles) > obstacle_count:
            obstacles.pop()
        while len(obstacles) < obstacle_count:
            pos = random_empty_position(sh, sw, snake, [a['pos'] for a in apples], obstacles)
            obstacles.append(pos)


    spawn_apples_and_obstacles()

    while True:
        now = time.time()

        key = stdscr.getch()
        if key != -1:
            if key == ord('p'):
                paused = not paused
            elif key == ord('o'):
                sound_on = not sound_on
            elif key in KEY_DIRECTION_MAP:
                new_dir = DIRECTIONS[KEY_DIRECTION_MAP[key]]
                new_head = [snake[0][0] + new_dir[0], snake[0][1] + new_dir[1]]
                if len(snake) < 2 or new_head != snake[1]:
                    dir_vec = new_dir
                speed_boost = True
            elif key in (ord('q'), 27):
                return score, int(now - start_time), sound_on, None
        else:
            speed_boost = False

        if paused:
            pause_msg = "Paused — press 'p' to resume"
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(sh // 2, sw // 2 - len(pause_msg)//2, pause_msg)
            stdscr.attroff(curses.A_REVERSE)
            stdscr.refresh()
            time.sleep(0.1)
            continue

        current_delay = max(min_delay, base_delay - (score // 5) * 0.01)
        if speed_boost:
            current_delay /= 3

        if now - last_move_time >= current_delay:
            last_move_time = now
            head = [snake[0][0] + dir_vec[0], snake[0][1] + dir_vec[1]]

            # Check collision with self, borders, obstacles
            if (head in snake or
                head[0] <= 0 or head[0] >= sh - 1 or
                head[1] <= 0 or head[1] > sw - SEGMENT_WIDTH - 1 or
                head in obstacles):
                return score, int(now - start_time), sound_on, True  # Game over

            snake.insert(0, head)

            ate_apple_idx = None
            for i, apple in enumerate(apples):
                if apple['pos'] == head:
                    ate_apple_idx = i
                    break

            if ate_apple_idx is not None:
                apple = apples.pop(ate_apple_idx)
                if apple.get('special', False):
                    score += 2
                    grow_segments += 2
                else:
                    score += 1
                    grow_segments += 1
                if sound_on:
                    play_sound()

                pos = random_empty_position(sh, sw, snake, [a['pos'] for a in apples], obstacles)
                color = random_color()
                apples.append({'pos': pos, 'color': color})

                spawn_apples_and_obstacles()

            if grow_segments > 0:
                grow_segments -= 1
            else:
                snake.pop()

        if now - last_draw_time >= timer_refresh_interval:
            last_draw_time = now
            elapsed = now - start_time

            score_str = f"Score: {score}"
            mins = int(elapsed // 60)
            secs = int(elapsed % 60)
            millis = int((elapsed - int(elapsed)) * 1000)
            time_str = f"Time: {mins:02d}:{secs:02d}.{millis:03d}"
            controls_str = f"Pause (P)  Sound ({'ON' if sound_on else 'OFF'}) (O)  Quit (Q)"

            left_pos = 2
            right_pos = sw - len(controls_str) - 2
            center_pos = (sw - len(time_str)) // 2

            stdscr.erase()
            stdscr.attron(curses.color_pair(10))  # border same color as snake
            stdscr.border()
            stdscr.attroff(curses.color_pair(10))

            stdscr.attron(curses.color_pair(10) | curses.A_BOLD)
            stdscr.addstr(0, left_pos, score_str)
            stdscr.addstr(0, center_pos, time_str)
            stdscr.addstr(0, right_pos, controls_str)
            stdscr.attroff(curses.color_pair(10) | curses.A_BOLD)

            for apple in apples:
                y, x = apple['pos']
                curses.init_pair(20 + apple['color'], apple['color'], -1)
                stdscr.attron(curses.color_pair(20 + apple['color']))
                stdscr.addstr(y, x, APPLE_CHAR if not apple.get('special', False) else SPECIAL_APPLE_CHAR)
                stdscr.attroff(curses.color_pair(20 + apple['color']))

            stdscr.attron(curses.color_pair(30))
            for y, x in obstacles:
                stdscr.addstr(y, x, OBSTACLE_CHAR)
            stdscr.attroff(curses.color_pair(30))

            stdscr.attron(curses.color_pair(10))
            for y, x in snake:
                stdscr.addstr(y, x, SNAKE_CHAR)
            stdscr.attroff(curses.color_pair(10))

            stdscr.refresh()

        time.sleep(0.01)


def main(stdscr):
    sound_on = True
    curses.curs_set(0)
    while True:
        sound_on = title_screen(stdscr, sound_on)
        score, elapsed, sound_on, game_over = run_game(stdscr, sound_on)

        # Only ask for name if the player lost (not quit)
        if game_over is True:
            name = ask_name(stdscr)
            add_score_to_leaderboard(name, score, elapsed)

        # Always show the Game Over screen
        stdscr.clear()
        stdscr.nodelay(False)
        sh, sw = stdscr.getmaxyx()
        msg = "GAME OVER"
        sub_msg = "(Q)uit to title or (R)etry"
        stdscr.attron(curses.A_BOLD)
        stdscr.addstr(sh // 2 - 1, sw // 2 - len(msg) // 2, msg)
        stdscr.attroff(curses.A_BOLD)
        stdscr.addstr(sh // 2 + 1, sw // 2 - len(sub_msg) // 2, sub_msg)
        stdscr.refresh()

        key = stdscr.getch()
        if key in (ord('q'), 27):
            continue  # Go back to title screen
        else:
            continue  # Restart game

if __name__ == '__main__':
    signal.signal(signal.SIGINT, lambda s, f: sys.exit(0))
    curses.wrapper(main)
