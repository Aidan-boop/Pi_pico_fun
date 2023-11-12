from machine import Pin, I2C, RTC      #importing relevant modules & classes
from time import sleep
import bme280       #importing BME280 library
from pimoroni import RGBLED, Button  # for led on display
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY_2 # for display
import random
import network
import secrets
import urequests
import ujson
import _thread

### INIT Code here ###
i2c=I2C(0,sda=Pin(0), scl=Pin(1), freq=400000)    #initializing the I2C method
# init display
display = PicoGraphics(display=DISPLAY_PICO_DISPLAY_2, rotate=0)
display.set_backlight(0.5)
WIDTH, HEIGHT = display.get_bounds()

# init colors you want to use for display
background = display.create_pen(102, 91, 148)
data = display.create_pen(255, 110, 199)
button = display.create_pen(172,194,210)
bar_colour = display.create_pen(100, 100, 100)
bright_blue = display.create_pen(117, 230, 218)
yellow = display.create_pen(230,218,117)
orange = display.create_pen(230,117,129)

BLACK = display.create_pen(0, 0, 0)
WHITE = display.create_pen(255, 255, 255)
display.set_font('bitmap8')
# init led
led = RGBLED(6, 7, 8)
led.set_rgb(0,0,0)
# init buttons
button_a = Button(12)
button_b = Button(13)
button_x = Button(14)
button_y = Button(15)
# init menu options
menu = ['Temperature', 'Game', 'Quote', 'Esp32', 'Sleep']
# sub_menu_temp = ['Temperature_live', 'Temperature_avg'] might add this to the ui instead of nested menu
sub_menu_games = ['Pong', 'Flappy', 'Invaders']
game_menu = ['Resume', 'Restart', 'Quit']
game_over = ['Restart', 'Quit']
sub_quote = ['Refresh', 'Quit']
curr = 'Temperature' # default to temperature
sub_menu = None
game_state = None
flag_game = 0
# init rtc module
rtc = RTC()
rtc.datetime((2023,01,20,4,18,14,0,0))
last_time = -1
###

def clear():
    display.set_pen(background)
    display.clear()
    display.update()

ship_scale = 0.4
#############################################
# spaceship class quick nav
#############################################
class Spaceship:
    def __init__(self, x, y, skin):
        self.skin = skin
        self.x = x
        self.y = y
        self.last_shoot_time = 0
        self.missile_dir = 2 if x == 20 else -2
        self.missile_skin = "*💈" if x == 20 else "+"

    @property
    def skin(self):
        return self._skin

    @skin.setter
    def skin(self, value):
        self._skin = value
        self._skin_length = display.measure_text(self.skin, scale = ship_scale)

    @property
    def skin_length(self):
        return self._skin_length

    def print_ship(self):
        display.text(self.skin, self.x, self.y, angle = 90, scale = ship_scale)

    def erase(self):
        display.text(" " * self.skin_length, self.x, self.y, angle = 90, scale = ship_scale)

    def move_left(self, delta):
        if self.y > 1 + delta:
            self.y -= delta
            display.text(self.skin, self.x, self.y, angle = 90, scale = ship_scale)

    def move_right(self, delta):
        if self.y < HEIGHT - self.skin_length - delta:
            self.y += delta
            display.text(self.skin, self.x, self.y, angle = 90, scale = ship_scale)


    def shoot(self):
        if abs(clock_time - self.last_shoot_time) >= 1:
            missiles.append(
                Missile(
                    self.missile_skin,
                    self.x + self.missile_dir,
                    self.y + self.skin_length // 2,
                    self.missile_dir,
                )
            )
            self.last_shoot_time = clock_time
#############################################
# missile class quick nav
#############################################
class Missile:
    def __init__(self, skin, x, y, dir_x):
        self.skin = skin[0]
        self.x = x
        self.y = y
        self.dir_x = dir_x
        self._destroyed = False
        self.flag_go = 0

    def move(self):    
        self.x += self.dir_x
        self._collide()
        if not self.destroyed:
           display.text(self.skin, self.x, self.y, scale = 1)

    def _collide(self):
        if self.dir_x > 0:
            for enemy in enemies[:]:
                if (
                    self.x == enemy.x
                    and enemy.y <= self.y < enemy.y + enemy.skin_length
                ):
                    self._destroyed = True
                    enemies.remove(enemy)
                    return
        else:
            if (
                self.x == spaceship.x
                and spaceship.y <= self.y < spaceship.y + spaceship.skin_length
            ):
                global flag_game
                flag_game = 1


    @property
    def destroyed(self):
        return not (1 < self.x < WIDTH - 1) or self._destroyed

#############################################
#invaders startup quick nav
#############################################

def invaders_startup():
    display.set_font('sans')
    friendly_ship = "||=^=||"
    enemy_ship = "|=V=|"
    SPACESHIP_Y = HEIGHT // 2
    spaceship = Spaceship(x = 20, y=SPACESHIP_Y, skin=friendly_ship)
    spaceship.print_ship()

    # missiles creation
    missiles = []

    # enemies creation
    enemies = []
    for x in range(5):
        for y in range(4):
            enemies.append(Spaceship(x=200 + x * 18, y=20 + y * 55, skin=enemy_ship))
            enemies[-1].print_ship()
    enemies_dir = -1
    enemies_moves_left = 0

    prev_clock_time_movement = rtc.datetime()[-2]
    prev_clock_time = rtc.datetime()[-2]
    return spaceship, SPACESHIP_Y, missiles, enemies, enemies_dir, enemies_moves_left, prev_clock_time_movement, prev_clock_time
#############################################  
# wifi class quick nav
#############################################
class connect_to_internet:
    def __init__(self):
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.api_key = secrets.openai_api
        self.endpoint = "https://api.openai.com/v1/completions"
        self.flag = 0
        self.quote = None
        self.input_data = ujson.dumps({
            "model": "text-davinci-003",
            "prompt": "random inspiring quote.",
            "max_tokens": 100,
            "temperature": 0.5
        })

        self.headers_data = {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + self.api_key
        }
        
    def establish_connection(self):
        # Wait for connect or fail
        self.wlan.connect(secrets.SSID, secrets.PASSWORD)
        max_wait = 10
        while max_wait > 0:
            if self.wlan.status() < 0 or self.wlan.status() >= 3:
                break
            max_wait -= 1
            print('waiting for connection...')
            sleep(1)
         
        # Handle connection error
        if self.wlan.status() != 3:
            self.flag = 0
            raise RuntimeError('network connection failed')
        else:
          print('connected')
          self.status = self.wlan.ifconfig()
          print( 'ip = ' + self.status[0] )
          self.flag = 1
          #self.quote = self.grab_quote()
          #return self.quote
          
    
    def grab_quote(self):
        if self.flag == 1:
            response = urequests.post(self.endpoint, headers=self.headers_data, data=self.input_data).json()
            return response['choices'][0]['text']
#############################################
# menu class quick nav
#############################################
class menus:
    def __init__(self, menu_to_use):
        self.menu = menu_to_use
        self.rec_width = 250
        self.margins = 10
        self.rec_height = 30
        self.size_txt = 3
        self.num_buttons = len(self.menu)
        self.middle = int((WIDTH - self.rec_width)/2)
        self.center = int((HEIGHT - (self.num_buttons-1)*self.margins - self.rec_height*self.num_buttons)/2) # total height - space taken up by menu
        self.center_button = int((self.rec_height - 24)/2)
        self.index = 0
        self.pointer = menu[0]
        
        
    def create_menu(self):
        for j in range(0, self.num_buttons):
            if j == self.index:
                display.set_pen(data)
            else: 
                display.set_pen(button)
            display.rectangle(self.middle, self.center + j*10 + j*self.rec_height, self.rec_width, self.rec_height)
            if j == self.index:
                display.set_pen(button)
            else: 
                display.set_pen(data)
            width_text = display.measure_text(self.menu[j], scale = self.size_txt)
            middle_text = int((WIDTH - width_text)/2)
            display.text(f'{self.menu[j]}', middle_text, self.center_button + self.center + j*10 + j*self.rec_height, 0, self.size_txt)
    
    def update_menu(self, prev_idx): # update menu colors at specific idx
        # first change colors of previous idx back
        display.set_pen(button)
        display.rectangle(self.middle, self.center + prev_idx*10 + prev_idx*self.rec_height, self.rec_width, self.rec_height)
        display.set_pen(data)
        width_text = display.measure_text(self.menu[prev_idx], scale = self.size_txt)
        middle_text = int((WIDTH - width_text)/2)
        display.text(f'{self.menu[prev_idx]}', middle_text, self.center_button + self.center + prev_idx*10 + prev_idx*self.rec_height, 0, self.size_txt)
        # change colors of selected button
        display.set_pen(data)
        display.rectangle(self.middle, self.center + self.index*10 + self.index*self.rec_height, self.rec_width, self.rec_height)
        display.set_pen(button)
        width_text = display.measure_text(self.menu[self.index], scale = self.size_txt)
        middle_text = int((WIDTH - width_text)/2)
        display.text(f'{self.menu[self.index]}', middle_text, self.center_button + self.center + self.index*10 + self.index*self.rec_height, 0, self.size_txt)
        
    def menu_poll(self):
        while 1:
            prev_index = self.index
            if button_a.read():
                self.index = self.index - 1
            elif button_b.read():
                self.index = self.index + 1
            if self.index < 0:
                self.index = self.num_buttons - 1
            self.index = self.index % self.num_buttons
            self.pointer = self.menu[self.index]
            self.update_menu(prev_index)
            display.update()
            if button_y.read():
                self.index = 0
                clear()
                return self.pointer
            if button_x.read():
                self.sub_menu_break()
                return None
    def sub_menu_break(self):
        global curr
        curr = None
    
    
pin = getattr(button_x, 'pin')
interrupt_flag = 0 
def callback(pin):
    global interrupt_flag
    interrupt_flag = 1

#############################################
# pong classes quick nav    
#############################################
class Ball:
    def __init__(self, x, y, r, dx, dy, pen):
        self.x = x
        self.y = y
        self.r = r
        self.dx = dx
        self.dy = dy
        self.pen = pen
        
class Bat:
    def __init__(self, y):
        self.y = y       

# initialise shapes
flag_avg = 1
avg_temp = None
avg_hum = None
avg_pres = None
integer_contains = '-0123456789.'

pin.irq(trigger=Pin.IRQ_RISING, handler=callback)
Quote = None
master_menu = menus(menu)
sub_menu_game = menus(sub_menu_games)
game_options = menus(game_menu)
game_done = menus(game_over)
quote_options = menus(sub_quote)

# ideally want this done in the background as well
connection = connect_to_internet()
flag_quote = 1

clear()
#############################################
# main loop quick nav
#############################################
while True:
    display.set_pen(background)
    display.clear()
    if button_x.read() or interrupt_flag:
        clear()
        master_menu.create_menu()
        display.update()
        curr = master_menu.menu_poll()
        sub_menu = None
        last_time = curr_time - 2
        interrupt_flag = 0
  
    bme = bme280.BME280(i2c=i2c)          #BME280 object created
    vals = bme.values
    temp = vals[0]
    pressure = vals[1]
    humidity = vals[2]
    curr_time = rtc.datetime()[-2]

#############################################
# temperature quick nav 
#############################################
    if curr == 'Temperature' and abs(curr_time - last_time) >= 2:
        # add sub menu with live vs avg or add avg to this ui somehow
        width_text_temp = display.measure_text("Temp", scale = 3)
        middle_text_temp = int((WIDTH/2 - width_text_temp)/2)
        width_temp = display.measure_text(temp, scale = 5)
        middle_temp = int((WIDTH/2 - width_temp)/2)
        width_pres = display.measure_text(pressure, scale = 5)
        middle_pres = int((WIDTH - width_pres)/2)
        width_text_pres = display.measure_text("Pressure", scale = 3)
        middle_text_pres = int((WIDTH - width_text_pres)/2)
        width_hum = display.measure_text(humidity, scale = 5)
        middle_hum = int((WIDTH/2 - width_hum)/2)
        width_text_hum = display.measure_text("Hum", scale = 3)
        middle_text_hum = int((WIDTH/2 - width_text_hum)/2)
        center = int((HEIGHT/2 - 20 - 40 - 16)/2)
        display.set_pen(data)
        display.text("Temp", middle_text_temp, center, wordwrap = WIDTH, spacing = 1, scale = 3)
        display.text(f"{temp}", middle_temp, center + 24 + 20, wordwrap = WIDTH, spacing = 1, scale = 5)
        display.text("Hum", WIDTH//2 +middle_text_hum, center, wordwrap = WIDTH, spacing = 1, scale = 3)
        display.text(f"{humidity}", WIDTH//2 + middle_hum, center + 24 + 20, wordwrap = WIDTH, spacing = 1, scale = 5)
        display.text("Pressure", middle_text_pres, center + HEIGHT//2, wordwrap = WIDTH, spacing = 1, scale = 3)
        display.text(f"{pressure}", middle_pres, center + HEIGHT//2 + 20 + 24, wordwrap = WIDTH, spacing = 1, scale = 5)
        display.update()
        if not flag_quote:
            connection.establish_connection()
            while Quote == None:
                try:
                    Quote = connection.grab_quote()
                except OSERROR:
                    print('error occured')
            flag_quote = 1
        last_time = rtc.datetime()[-2]
#############################################
# game quick nav 
#############################################
    elif curr == 'Game':
        if sub_menu == None and interrupt_flag == 0:
            display.set_pen(background)
            display.clear()
            sub_menu_game.create_menu()
            display.update()
            sub_menu = sub_menu_game.menu_poll()
            last_time = curr_time - 1
        if sub_menu != None:
            interrupt_flag = 0
#############################################
# pong quick nav 
#############################################
        if sub_menu == 'Pong' and abs(curr_time - last_time) >= 2:
            ball = Ball(random.randint(150, WIDTH), random.randint(75, HEIGHT), 8, 3, 3, data)
            bat = Bat(int((HEIGHT-20)/2))
            flag = 0
            flag2 = 0
            while 1:
                display.set_pen(background)
                display.clear()
                # game goes here
                ball.x += ball.dx
                ball.y += ball.dy
                    
                if ball.x <= 12:
                    if ball.y > bat.y + 40 or ball.y < bat.y: 
                        #display.set_led(255,0,0)
                        ball.dx =0
                        ball.dy =0
                        ball.x = 500
                        ball.y = 500
                        flag2 = 1
                    if abs(ball.dx) < 10.0:     
                        if flag:
                            ball.dx -= 0.5
                            ball.dy -= 0.5
                            print(ball.dx)
                            print(ball.dy)
                            print('-------------')
                        else:
                            ball.dx += 0.5
                            ball.dy += 0.5
                            print('+++++++++++++')
                            print(ball.dx)
                            print(ball.dy)
                            print('+++++++++++++')
                if ball.x < 12 or ball.x > WIDTH - 4:
                    ball.dx *= -1
                    flag = flag ^ 1
                if ball.y < 4 or ball.y > HEIGHT - 4:
                    ball.dy *= -1
                if not flag2:  
                    display.set_pen(data)
                    display.circle(int(ball.x), int(ball.y), int(ball.r))
        
                if button_b.read() and bat.y < HEIGHT - 40:
                    bat.y = bat.y + 10
                if button_a.read() and bat.y > 0:
                    bat.y = bat.y - 10
                if not flag2:
                    display.set_pen(bar_colour)
                    display.rectangle(0, bat.y, 10, 40)
                if button_x.read() or flag2:
                    display.set_pen(background)
                    display.clear()
                    if flag_game:
                        game_done.create_menu()
                        display.update()
                        game_state = game_done.menu_poll()
                    else:
                        game_options.create_menu()
                        display.update()
                        game_state = game_options.menu_poll()
                    if game_state == 'Quit':
                        game_state = None
                        break
                    elif game_state== 'Restart':
                        display.set_pen(background)
                        display.clear()
                        ball = Ball(random.randint(150, WIDTH -10), random.randint(75, HEIGHT- 10), 8, 3, 3, data)
                        bat = Bat(1)
                        game_state = None
                        flag2 = 0
                        flag = 0
                    else:
                        game_state = None
                    
                                
                display.update()
                continue
            sub_menu = None
            last_time = rtc.datetime()[-2]
######################################################
# flappy quick nav            
######################################################
        elif sub_menu == 'Flappy' and abs(curr_time - last_time) >= 2:
            #pipes
            class pipes_creator:
                def __init__(self):
                    self.gap = 85
                    self.width = 30
                    self.dx = 5
                    self.x = WIDTH - self.width
                    self.y2 = random.randrange(self.gap + 30, HEIGHT - 10 - 30, 15)
                    self.y1 = self.y2 - self.gap
                        



            def collision(bird_x, bird_y, bird_width, pipe : object, ground_height):
                if pipe.x <= bird_x + bird_width//2 < (pipe.x + pipe.width) or pipe.x <= bird_x - bird_width//2 < (pipe.x + pipe.width):
                    # this means collision could occur
                    if bird_y + 9 >= pipe.y2 or bird_y - 9 <= (pipe.y2 - pipe.gap):
                        global game_over
                        game_over = 1

            def make_ground(x):
                for i in range(x, 330, 10):
                    display.triangle(i, HEIGHT, i + 5, HEIGHT - 10, i+10, HEIGHT)
                    
            def startup_flappy():        
                #INIT stuff
                pipes = []
                pipes.append(pipes_creator())
                #flags
                game_over = 0
                # used to limit pipe creation
                flag_create = 1
                # used for initial stand still
                flag_first = 1
                # bird
                bird_x = 50
                bird_y = HEIGHT//2
                bird_dy = 0
                bird_width = 18
                bird_height = 18
                # ground
                ground_height = 10
                ground_x = 0
                # point counter
                counter = 0
                #bird_dx = 0
                display.set_font('sans')
                display.set_pen(data)
                #bird
                display.set_pen(yellow)
                display.circle(bird_x, bird_y, 9)
                display.set_pen(orange)
                display.triangle(bird_x + 7, bird_y + 5, bird_x + 7, bird_y - 5, bird_x + 15, bird_y)
                display.set_pen(data)
                #pipes
                display.rectangle(pipes[0].x, 0, pipes[0].width, pipes[0].y1)
                display.rectangle(pipes[0].x, pipes[0].y2, pipes[0].width, HEIGHT - pipes[0].y2)
                #ground
                display.set_pen(bright_blue)
                make_ground(ground_x)
                display.set_pen(data)
                display.update()
                return pipes, bird_y, bird_x, bird_dy, bird_width, bird_height, ground_height, ground_x, counter, game_over, flag_create, flag_first
            [pipes, bird_y, bird_x, bird_dy, bird_width, bird_height, ground_height, ground_x, counter, game_over, flag_create, flag_first] = startup_flappy()

            while True:
                if flag_first:
                    while not button_b.read():
                        continue
                    bird_dy = -15
                    flag_first = 0
                # clear display for updated positions
                display.set_pen(background)
                display.clear()
                display.set_pen(data)
                # this is for sliding ground effect
                if ground_x == -10:
                    ground_x = 0
                #jump
                if button_b.read():
                    bird_dy = -15
                #falling
                bird_dy += 2
                bird_y += bird_dy
                # bound checking
                if bird_y == 0:
                    bird_dy = 0
                if bird_y >= HEIGHT - 20:
                    game_over = 1
                ####################################
                display.set_pen(yellow)
                display.circle(bird_x, bird_y, 9)
                display.set_pen(orange)
                display.triangle(bird_x + 7, bird_y + 5, bird_x + 7, bird_y - 5, bird_x + 15, bird_y)
                display.set_pen(data)
                for pipe in pipes:
                    pipe.x -= pipe.dx
                    display.rectangle(pipe.x, 0, pipe.width, pipe.y1)
                    display.rectangle(pipe.x, pipe.y2, pipe.width, HEIGHT - pipe.y2)
                if pipes[0].x <= 100 and flag_create == 1:
                    pipes.append(pipes_creator())
                    flag_create = 0
                if pipes[0].x <= 0:
                    flag_create = 1
                    pipes.remove(pipes[0])
                    counter += 1
                
                ground_x -= 5   
                display.set_pen(bright_blue)
                make_ground(ground_x)
                display.set_pen(data)
                display.set_pen(WHITE)
                display.text(str(counter), WIDTH // 2, 30, scale = 1.5)
                display.set_pen(data)
                display.update()
                collision(bird_x, bird_y, bird_width, pipes[0], ground_height)
                ################################
                # Game over
                ################################
                if game_over:
                    while bird_y < HEIGHT - ground_height:
                        display.set_pen(background)
                        display.clear()
                        display.set_pen(data)
                        bird_y += 4
                        display.set_pen(yellow)
                        display.circle(bird_x, bird_y, 9)
                        display.set_pen(orange)
                        display.triangle(bird_x + 7, bird_y + 5, bird_x + 7, bird_y - 5, bird_x + 15, bird_y)
                        display.set_pen(data)
                        for pipe in pipes:
                            display.rectangle(pipe.x, 0, pipe.width, pipe.y1)
                            display.rectangle(pipe.x, pipe.y2, pipe.width, HEIGHT - pipe.y2)
                        display.set_pen(bright_blue)
                        make_ground(ground_x)
                        display.set_pen(data)
                        display.set_pen(WHITE)
                        display.text(str(counter), WIDTH // 2, 30, scale = 1.5)
                        display.set_pen(data)
                        display.update()
                ################################
                # menu
                ################################
                if button_x.read() or game_over:
                    display.set_font('bitmap8')
                    display.set_pen(background)
                    display.clear()
                    if game_over:
                        game_done.create_menu()
                        display.update()
                        game_state = game_done.menu_poll()
                    else:
                        game_options.create_menu()
                        display.update()
                        game_state = game_options.menu_poll()
                    if game_state == 'Quit':
                        game_state = None
                        interrupt_flag = 0
                        break
                    elif game_state== 'Restart':
                        display.set_pen(background)
                        display.clear()
                        [pipes, bird_y, bird_x, bird_dy, bird_width, bird_height, ground_height, ground_x, counter, game_over, flag_create, flag_first] = startup_flappy()
                        game_state = None
                    else:
                        display.set_font('sans')
                        game_state = None
            sub_menu = None
            last_time = rtc.datetime()[-2]
######################################################
# invaders quick nav          
######################################################
        elif sub_menu == 'Invaders' and abs(curr_time - last_time) >= 2:
            spaceship, SPACESHIP_Y, missiles, enemies, enemies_dir, enemies_moves_left, prev_clock_time_movement, prev_clock_time = invaders_startup()
            while True:
                # spaceship management
                # left and right movement with bound
                display.set_pen(background)
                display.clear()
                display.set_pen(data)
                clock_time = rtc.datetime()[-2]
                if button_b.read():
                    spaceship.move_right(3)
                elif button_a.read():
                    spaceship.move_left(3)
                else:
                    spaceship.print_ship()
                # movement 
                if button_y.read():
                    spaceship.shoot()

                # missiles management
                for missile in missiles[:]:
                    missile.move()
                    if missile.destroyed:
                        missiles.remove(missile)

                # enemies management
                if abs(clock_time-prev_clock_time_movement) >= 2:
                    prev_clock_time_movement = clock_time
                    # also has to be getting at least here
                    if enemies_moves_left:
                        enemies_moves_left -= 1
                        for enemy in enemies:
                            if enemies_dir > 0:
                                enemy.move_right(1)
                            else:
                                enemy.move_left(1)
                    else:
                        enemies_moves_left = 10
                        enemies_dir = -enemies_dir
                if enemies:
                    for enemy in enemies:
                        enemy.print_ship()
                    if abs(clock_time - prev_clock_time) >= 2:
                        if len(enemies) == 1:
                            enemy = enemies[0]
                            enemy.missile_dir = -1
                        prev_clock_time = clock_time
                        random.choice(enemies).shoot()
                else:
                    flag_game = 1
                display.update()
                # Detect game over or menu
                if button_x.read() or flag_game:
                    display.set_font('bitmap8')
                    display.set_pen(background)
                    display.clear()
                    if flag_game:
                        game_done.create_menu()
                        display.update()
                        game_state = game_done.menu_poll()
                    else:
                        game_options.create_menu()
                        display.update()
                        game_state = game_options.menu_poll()

                    if game_state == 'Quit':
                        game_state = None
                        flag_game = 0
                        break
                    elif game_state== 'Restart':
                        flag_game = 0
                        spaceship, SPACESHIP_Y, missiles, enemies, enemies_dir, enemies_moves_left, prev_clock_time_movement, prev_clock_time = invaders_startup()
                    else:
                        display.set_font('sans')
                        flag_game = 0 
                        game_state = None
                sub_menu = None
        display.set_font('bitmap8')   
#############################################
# quote quick nav 
#############################################      
    elif curr == 'Quote' and abs(curr_time - last_time) >= 2:
        display.set_pen(data)
        display.text(f'{Quote}',  20, 10, wordwrap = (WIDTH - 50), scale = 3)
        display.update()
        while 1:
            if button_x.read():
                quote_state = None
                display.set_pen(background)
                display.clear()
                quote_options.create_menu()
                display.update()
                quote_state = quote_options.menu_poll()
                if quote_state == 'Refresh':
                    display.set_pen(data)
                    display.text(f'{Quote}',  20, 10, wordwrap = (WIDTH - 50), scale = 3)
                    display.update()
                    prev_quote = Quote
                    while Quote == prev_quote:
                        try:
                            Quote = connection.grab_quote()
                        except OSERROR:
                            print('error occured')
                    display.set_pen(background)
                    display.clear()
                    display.set_pen(data)
                    display.text(f'{Quote}',  20, 10, wordwrap = (WIDTH - 50), scale = 3)
                    display.update()
                    interrupt_flag = 0
                elif quote_state == None:
                    display.set_pen(background)
                    display.clear()
                    display.set_pen(data)
                    display.text(f'{Quote}',  20, 10, wordwrap = (WIDTH - 50), scale = 3)
                    display.update()
                else:
                    break
        
        last_time = rtc.datetime()[-2]
#############################################
# esp quick nav 
#############################################
    elif curr == 'Esp32' and abs(curr_time - last_time) >= 2:
        display.set_pen(data)
        display.text('Esp32 is under devlopment', 10, 3, wordwrap = (WIDTH - 10), scale = 4)
        display.update()
        last_time = rtc.datetime()[-2]
#############################################
# sleep quick nav 
#############################################
    elif curr == 'Sleep' and abs(curr_time - last_time) >= 2:
        display.set_backlight(0)
        clear()
        while 1:
            if button_x.read():
                display.set_backlight(0.5)
                display.update()
                connection.establish_connection()
                break
        last_time = rtc.datetime()[-2]

