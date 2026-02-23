"""
Cat's Undertale – Famicom Edition
No external music files – purely procedural, sounding like UNDERTALE on an NES.
"""

import pygame
import numpy as np
import sys
import math
import random

# ==================== CONFIGURATION ====================
GBA_WIDTH, GBA_HEIGHT = 240, 160
SCALE = 3
SCREEN_SIZE = (GBA_WIDTH * SCALE, GBA_HEIGHT * SCALE)
TILE_SIZE = 16
FPS = 60

COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_RUINS = (100, 70, 120)
COLOR_SNOW = (200, 230, 255)
COLOR_WATER = (80, 160, 200)
COLOR_HOTLAND = (200, 100, 50)
COLOR_CORE = (150, 80, 80)
COLOR_CAT = (210, 180, 140)
COLOR_ENEMY = (255, 100, 100)
COLOR_WALL = (0, 0, 0)

# ==================== EMBEDDED LEVEL DATA ====================
LEVELS = {
    "ruins": [
        "###############",
        "#.............#",
        "#.###.###.###.#",
        "#.#.........#.#",
        "#.#...###...#.#",
        "#.#.E.....E.#.#",
        "#.#...###...#.#",
        "#.###########.#",
        "#.............#",
        "###############"
    ],
    "snowdin": [
        "###############",
        "#.............#",
        "#.##.....##...#",
        "#.............#",
        "#...##.E.##...#",
        "#.............#",
        "#.##.....##...#",
        "#.......E.....#",
        "#.............#",
        "###############"
    ],
    "waterfall": [
        "###############",
        "#.............#",
        "#.#########...#",
        "#.........#...#",
        "#.#######.#...#",
        "#.#...E...#...#",
        "#.#.......#...#",
        "#.#########...#",
        "#.............#",
        "###############"
    ],
    "hotland": [
        "###############",
        "#.............#",
        "#.####.####...#",
        "#.#...........#",
        "#.#..####..#..#",
        "#....E..E..#..#",
        "#.#..####..#..#",
        "#.#...........#",
        "#.####.####...#",
        "###############"
    ],
    "core": [
        "###############",
        "#.............#",
        "#.##.....##...#",
        "#.#.......#...#",
        "#.#..###..#...#",
        "#....E.E......#",
        "#.#..###..#...#",
        "#.#.......#...#",
        "#.##.....##...#",
        "###############"
    ],
    "last": [
        "###############",
        "#.............#",
        "#..#.....#....#",
        "#..#.....#....#",
        "#..#..E..#....#",
        "#..#.....#....#",
        "#..#.....#....#",
        "#.............#",
        "#.............#",
        "###############"
    ]
}

# ==================== FAMICOM SOUND MANAGER ====================
class SoundManager:
    """Procedural Famicom‑style music generator – no external files."""
    def __init__(self):
        self.mixer_available = True
        self.music_channel = None
        self.proc_channels = []

        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=512)
            self.music_channel = pygame.mixer.Channel(0)      # not used (fileless)
            self.proc_channels = [pygame.mixer.Channel(i) for i in range(1, 4)]
        except Exception as e:
            print(f"Warning: Could not initialize mixer ({e}). Sound disabled.")
            self.mixer_available = False

        self.current_level = None
        self.route = "pacifist"
        self.target_volume = 0.5
        self.current_volume = 0.5
        self.speed = 0.0
        self.enemy_near = False

        # Procedural storage
        self.proc_sounds = {}
        self.proc_target_volumes = [0.5, 0.5, 0.5]
        self.proc_current_volumes = [0.0, 0.0, 0.0]

    # ---------- Famicom waveform generators ----------
    def _pulse_wave(self, freq, duration, duty, volume):
        """
        Generate a pulse wave with given duty cycle (0.0–1.0).
        duty = 0.125, 0.25, 0.5, 0.75  (typical NES values)
        """
        try:
            sample_rate = pygame.mixer.get_init()[0]
            samples = int(duration * sample_rate)
            if samples <= 0:
                return None
            t = np.linspace(0, duration, samples, endpoint=False)
            # Square wave with duty cycle
            wave = np.where((t * freq) % 1.0 < duty, 1.0, -1.0)
            # Simple volume envelope (quick fade in/out to avoid clicks)
            envelope = np.ones(samples)
            fade = int(0.005 * sample_rate)
            if fade > 0:
                envelope[:fade] = np.linspace(0, 1, fade)
                envelope[-fade:] = np.linspace(1, 0, fade)
            wave *= envelope * volume
            wave = (wave * 32767).astype(np.int16)
            stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
            return pygame.sndarray.make_sound(stereo)
        except Exception:
            return None

    def _triangle_wave(self, freq, duration, volume):
        """Generate a triangle wave (clean, hollow sound)."""
        try:
            sample_rate = pygame.mixer.get_init()[0]
            samples = int(duration * sample_rate)
            if samples <= 0:
                return None
            t = np.linspace(0, duration, samples, endpoint=False)
            # Triangle wave: 2 * abs(2*(t*freq - floor(t*freq+0.5))) - 1
            phase = t * freq - np.floor(t * freq)
            wave = 2 * np.abs(2 * phase - 1) - 1
            envelope = np.ones(samples)
            fade = int(0.005 * sample_rate)
            if fade > 0:
                envelope[:fade] = np.linspace(0, 1, fade)
                envelope[-fade:] = np.linspace(1, 0, fade)
            wave *= envelope * volume
            wave = (wave * 32767).astype(np.int16)
            stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
            return pygame.sndarray.make_sound(stereo)
        except Exception:
            return None

    def _noise(self, duration, volume, mode='white'):
        """Generate noise (for drums/percussion)."""
        try:
            sample_rate = pygame.mixer.get_init()[0]
            samples = int(duration * sample_rate)
            if samples <= 0:
                return None
            if mode == 'white':
                wave = np.random.uniform(-1, 1, samples)
            else:  # 'periodic' – NES noise can be periodic
                # simple approximation: random but with a slight pattern
                wave = np.random.uniform(-1, 1, samples)
                wave[::2] *= 0.7   # add some texture
            envelope = np.ones(samples)
            fade = int(0.003 * sample_rate)
            if fade > 0:
                envelope[:fade] = np.linspace(0, 1, fade)
                envelope[-fade:] = np.linspace(1, 0, fade)
            wave *= envelope * volume
            wave = (wave * 32767).astype(np.int16)
            stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
            return pygame.sndarray.make_sound(stereo)
        except Exception:
            return None

    # ---------- Famicom drum kit ----------
    def _drum(self, duration, type='kick', volume=0.5):
        """Create a drum sound using noise and triangle/pulse."""
        if type == 'kick':
            # Kick: short low pulse + noise decay
            try:
                sample_rate = pygame.mixer.get_init()[0]
                samples = int(duration * sample_rate)
                if samples <= 0:
                    return None
                t = np.linspace(0, duration, samples, endpoint=False)
                # fast descending pitch on triangle
                pitch = 120 * np.exp(-t * 20)
                kick_tone = np.sin(2 * np.pi * pitch * t) * np.exp(-t * 20)
                # add a little noise slap
                noise = np.random.uniform(-0.3, 0.3, samples) * np.exp(-t * 30)
                wave = kick_tone + noise
                wave *= volume
                wave = (wave * 32767).astype(np.int16)
                stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
                return pygame.sndarray.make_sound(stereo)
            except Exception:
                return None
        elif type == 'snare':
            # Snare: mix of noise and a high tone
            try:
                sample_rate = pygame.mixer.get_init()[0]
                samples = int(duration * sample_rate)
                if samples <= 0:
                    return None
                t = np.linspace(0, duration, samples, endpoint=False)
                noise = np.random.uniform(-1, 1, samples) * np.exp(-t * 20)
                tone = np.sin(2 * np.pi * 180 * t) * np.exp(-t * 15)
                wave = 0.6 * noise + 0.4 * tone
                wave *= volume
                wave = (wave * 32767).astype(np.int16)
                stereo = np.repeat(wave.reshape(-1, 1), 2, axis=1)
                return pygame.sndarray.make_sound(stereo)
            except Exception:
                return None
        elif type == 'hat':
            # Hi‑hat: short noise burst
            return self._noise(duration, volume * 0.7, mode='white')
        else:
            return None

    # ---------- Procedural loop generation ----------
    def _generate_famicom_loop(self, level_name, duration=4.0):
        """
        Create a 4‑second loop using Famicom channels:
        - Bass: triangle wave
        - Melody: pulse wave (50% duty)
        - Drums: noise + pulse for kick/snare
        """
        if not self.mixer_available:
            return None

        try:
            # Define musical parameters (note sequences reminiscent of UNDERTALE)
            if level_name == "ruins":
                # "Once Upon a Time" style
                bass_freqs = [110, 110, 98, 98]      # A, A, G, G
                melody_notes = [220, 262, 294, 330, 0, 330, 294, 262]
                tempo = 120
                duty = 0.5                           # 50% pulse for melody
            elif level_name == "snowdin":
                # "Snowy" feel
                bass_freqs = [98, 98, 110, 110]      # G, G, A, A
                melody_notes = [330, 294, 262, 220, 0, 220, 262, 294]
                tempo = 140
                duty = 0.25                           # 25% pulse for brighter sound
            elif level_name == "waterfall":
                # "Waterfall" calm
                bass_freqs = [65, 65, 73, 73]        # C, C, D, D
                melody_notes = [196, 220, 262, 294, 0, 262, 220, 196]
                tempo = 100
                duty = 0.5
            elif level_name == "hotland":
                # "Hotland" tense
                bass_freqs = [82, 82, 92, 92]        # E, E, F#, F#
                melody_notes = [330, 311, 294, 262, 0, 294, 311, 330]
                tempo = 160
                duty = 0.125                          # 12.5% for raspy lead
            elif level_name == "core":
                # "CORE" mechanical
                bass_freqs = [110, 98, 110, 98]      # A, G, A, G
                melody_notes = [349, 330, 311, 294, 0, 294, 311, 330]
                tempo = 180
                duty = 0.75                           # 75% for thick sound
            else:  # last
                # "Hopes and Dreams" / "SAVE the World" vibe
                bass_freqs = [65, 73, 65, 73]        # C, D, C, D
                melody_notes = [220, 262, 330, 392, 0, 392, 330, 262]
                tempo = 200
                duty = 0.5

            beat_duration = 60.0 / tempo
            sample_rate = pygame.mixer.get_init()[0]
            samples_per_beat = int(beat_duration * sample_rate)
            if samples_per_beat <= 0:
                return None

            # ---------- Bass (triangle) ----------
            bass_pattern = []
            for freq in bass_freqs:
                if freq == 0:
                    bass_pattern.append(np.zeros(samples_per_beat))
                else:
                    tone = self._triangle_wave(freq, beat_duration, volume=0.5)
                    if tone is None:
                        return None
                    arr = pygame.sndarray.array(tone)
                    if arr.size == 0:
                        return None
                    bass_pattern.append(arr[:, 0])   # take mono
            bass_array = np.concatenate(bass_pattern)
            repeats = int(duration / (len(bass_freqs) * beat_duration))
            if repeats > 0:
                bass_array = np.tile(bass_array, repeats)

            # ---------- Melody (pulse) ----------
            melody_pattern = []
            for note in melody_notes:
                if note == 0:
                    melody_pattern.append(np.zeros(samples_per_beat))
                else:
                    tone = self._pulse_wave(note, beat_duration, duty, volume=0.4)
                    if tone is None:
                        return None
                    arr = pygame.sndarray.array(tone)
                    if arr.size == 0:
                        return None
                    melody_pattern.append(arr[:, 0])
            melody_array = np.concatenate(melody_pattern)
            repeats = int(duration / (len(melody_notes) * beat_duration))
            if repeats > 0:
                melody_array = np.tile(melody_array, repeats)

            # ---------- Drums (noise + pulse) ----------
            drums_pattern = []
            for i in range(16):   # 16 beats per pattern
                if i % 4 == 0:    # kick on quarter notes
                    drum = self._drum(beat_duration, 'kick', 0.6)
                elif i % 8 == 6:  # snare on off-beats
                    drum = self._drum(beat_duration, 'snare', 0.5)
                elif i % 2 == 1:  # hi-hat on eighth notes
                    drum = self._drum(beat_duration, 'hat', 0.3)
                else:
                    drums_pattern.append(np.zeros(samples_per_beat))
                    continue
                if drum is None:
                    return None
                arr = pygame.sndarray.array(drum)
                if arr.size == 0:
                    return None
                drums_pattern.append(arr[:, 0])
            drums_array = np.concatenate(drums_pattern)
            repeats = int(duration / (16 * beat_duration))
            if repeats > 0:
                drums_array = np.tile(drums_array, repeats)

            # Trim to exact duration
            target_samples = int(duration * sample_rate)
            if target_samples <= 0:
                return None
            bass_array = bass_array[:target_samples]
            melody_array = melody_array[:target_samples]
            drums_array = drums_array[:target_samples]

            # Convert mono arrays to stereo sounds
            def to_stereo(mono):
                try:
                    if mono.size == 0:
                        return None
                    stereo = np.repeat(mono.reshape(-1, 1), 2, axis=1)
                    return pygame.sndarray.make_sound(stereo.astype(np.int16))
                except Exception:
                    return None

            bass_snd = to_stereo(bass_array)
            melody_snd = to_stereo(melody_array)
            drums_snd = to_stereo(drums_array)

            if bass_snd is None or melody_snd is None or drums_snd is None:
                return None

            return (bass_snd, melody_snd, drums_snd)

        except Exception as e:
            print(f"Famicom generation failed: {e}")
            return None

    def load_level(self, level_name):
        """Always use procedural Famicom music (no external files)."""
        if not self.mixer_available:
            return
        if level_name == self.current_level:
            return
        self.current_level = level_name

        # Stop any currently playing sounds
        for ch in self.proc_channels:
            try:
                ch.stop()
            except:
                pass

        # Generate or retrieve cached loop
        if level_name in self.proc_sounds:
            loops = self.proc_sounds[level_name]
        else:
            loops = self._generate_famicom_loop(level_name, duration=4.0)
            if loops is None:
                print("Famicom generation failed; disabling sound.")
                self.mixer_available = False
                return
            self.proc_sounds[level_name] = loops

        bass, melody, drums = loops
        try:
            self.proc_channels[0].play(bass, loops=-1)
            self.proc_channels[1].play(melody, loops=-1)
            self.proc_channels[2].play(drums, loops=-1)
        except Exception as e:
            print(f"Failed to play procedural music: {e}")
            self.mixer_available = False
            return

        self.proc_target_volumes = [0.5, 0.5, 0.5]
        self.proc_current_volumes = [0.0, 0.0, 0.0]

    def set_route(self, route):
        if route != self.route:
            self.route = route
            if self.current_level == "last":
                self.load_level("last")

    def update(self, player_speed, enemy_near):
        if not self.mixer_available:
            return
        self.speed = player_speed
        self.enemy_near = enemy_near

        base_vol = 0.3 + 0.4 * min(1.0, self.speed / 5.0)
        if enemy_near:
            base_vol *= 0.5
        self.target_volume = base_vol

        for i in range(3):
            diff = self.target_volume - self.proc_current_volumes[i]
            self.proc_current_volumes[i] += diff * 0.1
            if i < len(self.proc_channels):
                try:
                    self.proc_channels[i].set_volume(self.proc_current_volumes[i])
                except:
                    pass

# ==================== GAME OBJECTS (unchanged) ====================
class Cat(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self.image.fill(COLOR_CAT)
        pygame.draw.circle(self.image, COLOR_BLACK, (4, 4), 2)
        pygame.draw.circle(self.image, COLOR_BLACK, (12, 4), 2)
        pygame.draw.polygon(self.image, COLOR_BLACK, [(2,2), (0,0), (4,0)])
        pygame.draw.polygon(self.image, COLOR_BLACK, [(14,2), (12,0), (16,0)])
        self.rect = self.image.get_rect(topleft=(x, y))
        self.vx = self.vy = 0
        self.speed = 3

    def update(self, walls):
        self.rect.x += self.vx
        self.collide(self.vx, 0, walls)
        self.rect.y += self.vy
        self.collide(0, self.vy, walls)

    def collide(self, dx, dy, walls):
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                if dx > 0:
                    self.rect.right = wall.rect.left
                if dx < 0:
                    self.rect.left = wall.rect.right
                if dy > 0:
                    self.rect.bottom = wall.rect.top
                if dy < 0:
                    self.rect.top = wall.rect.bottom

class Wall(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self.image.fill(COLOR_BLACK)
        self.rect = self.image.get_rect(topleft=(x, y))

class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, level):
        super().__init__()
        self.image = pygame.Surface((TILE_SIZE, TILE_SIZE))
        self.image.fill(COLOR_ENEMY)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.direction = 1
        self.speed = 1
        self.level = level

    def update(self, walls):
        self.rect.x += self.speed * self.direction
        if self.rect.left <= 0 or self.rect.right >= GBA_WIDTH:
            self.direction *= -1
        for wall in walls:
            if self.rect.colliderect(wall.rect):
                self.direction *= -1
                self.rect.x += self.speed * self.direction

# ==================== MAIN GAME (unchanged) ====================
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption("Cat's Undertale (Famicom OST)")
        self.clock = pygame.time.Clock()
        self.running = True

        self.level_names = ["ruins", "snowdin", "waterfall", "hotland", "core", "last"]
        self.current_level_idx = 0
        self.level = self.level_names[self.current_level_idx]

        self.player = None
        self.walls = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.load_level(self.level)

        self.sound = SoundManager()
        self.sound.load_level(self.level)

    def load_level(self, level_name):
        self.walls.empty()
        self.enemies.empty()
        level_data = LEVELS[level_name]
        for row, line in enumerate(level_data):
            for col, char in enumerate(line):
                x = col * TILE_SIZE
                y = row * TILE_SIZE
                if char == '#':
                    self.walls.add(Wall(x, y))
                elif char == 'E':
                    self.enemies.add(Enemy(x, y, level_name))
        for row, line in enumerate(level_data):
            for col, char in enumerate(line):
                if char == '.':
                    self.player = Cat(col * TILE_SIZE, row * TILE_SIZE)
                    return

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            self.handle_events()
            self.update(dt)
            self.draw()
        pygame.quit()
        sys.exit()

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_LEFT:
                    self.player.vx = -self.player.speed
                elif event.key == pygame.K_RIGHT:
                    self.player.vx = self.player.speed
                elif event.key == pygame.K_UP:
                    self.player.vy = -self.player.speed
                elif event.key == pygame.K_DOWN:
                    self.player.vy = self.player.speed
                elif event.key == pygame.K_n:
                    self.current_level_idx = (self.current_level_idx + 1) % len(self.level_names)
                    self.level = self.level_names[self.current_level_idx]
                    self.load_level(self.level)
                    self.sound.load_level(self.level)
                elif event.key == pygame.K_p:
                    self.sound.set_route("pacifist")
                elif event.key == pygame.K_g:
                    self.sound.set_route("genocide")
            elif event.type == pygame.KEYUP:
                if event.key in (pygame.K_LEFT, pygame.K_RIGHT):
                    self.player.vx = 0
                if event.key in (pygame.K_UP, pygame.K_DOWN):
                    self.player.vy = 0

    def update(self, dt):
        self.player.update(self.walls)
        self.enemies.update(self.walls)

        enemy_near = any(abs(e.rect.centerx - self.player.rect.centerx) < 48 and
                         abs(e.rect.centery - self.player.rect.centery) < 48
                         for e in self.enemies)
        speed_mag = math.hypot(self.player.vx, self.player.vy)

        self.sound.update(speed_mag, enemy_near)

    def draw(self):
        if self.level == "ruins":
            bg_color = COLOR_RUINS
        elif self.level == "snowdin":
            bg_color = COLOR_SNOW
        elif self.level == "waterfall":
            bg_color = COLOR_WATER
        elif self.level == "hotland":
            bg_color = COLOR_HOTLAND
        elif self.level == "core":
            bg_color = COLOR_CORE
        else:
            bg_color = COLOR_CORE

        self.screen.fill(bg_color)

        scale = SCALE
        for sprite in self.walls:
            scaled_rect = pygame.Rect(sprite.rect.x * scale, sprite.rect.y * scale,
                                      TILE_SIZE * scale, TILE_SIZE * scale)
            pygame.draw.rect(self.screen, COLOR_WALL, scaled_rect)

        for sprite in self.enemies:
            scaled_rect = pygame.Rect(sprite.rect.x * scale, sprite.rect.y * scale,
                                      TILE_SIZE * scale, TILE_SIZE * scale)
            pygame.draw.rect(self.screen, COLOR_ENEMY, scaled_rect)

        player_scaled = pygame.transform.scale(self.player.image,
                                               (TILE_SIZE * scale, TILE_SIZE * scale))
        self.screen.blit(player_scaled, (self.player.rect.x * scale, self.player.rect.y * scale))

        pygame.display.flip()

# ==================== ENTRY POINT ====================
if __name__ == "__main__":
    game = Game()
    game.run()
