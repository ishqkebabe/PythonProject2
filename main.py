import random
import sys
import pygame

# =============================
# Undertale-like styling
# =============================
PALETTE = {
    "bg": (0, 0, 0),
    "fg": (255, 255, 255),
    "mid": (150, 150, 150),
    "dim": (70, 70, 70),
}

VIRTUAL_W, VIRTUAL_H = 480, 270
SCALE = 3
WINDOW_W, WINDOW_H = VIRTUAL_W * SCALE, VIRTUAL_H * SCALE
FPS = 60

HUD_H = 56
MARGIN = 16

CARD_W, CARD_H = 54, 70
CARD_GAP = 10

# Big text flash timing (ms)
FLASH_DURATION_MS = 900

# =============================
# Blackjack data
# =============================
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
RANK_VALUE = {
    "A": 11, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7,
    "8": 8, "9": 9, "10": 10, "J": 10, "Q": 10, "K": 10
}


class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit

    def __repr__(self):
        return f"{self.rank}{self.suit}"


class Deck:
    def __init__(self, num_decks=2):
        self.num_decks = num_decks
        self.cards = []
        self._build()

    def _build(self):
        self.cards = []
        for _ in range(self.num_decks):
            for s in SUITS:
                for r in RANKS:
                    self.cards.append(Card(r, s))
        random.shuffle(self.cards)

    def draw(self):
        if not self.cards:
            self._build()
        return self.cards.pop()


def hand_value(hand):
    total = 0
    aces = 0
    for c in hand:
        total += RANK_VALUE[c.rank]
        if c.rank == "A":
            aces += 1
    while total > 21 and aces > 0:
        total -= 10
        aces -= 1
    return total


# =============================
# Jokers (Power-ups)
# =============================
class Joker:
    name = "Joker"
    desc = "Does something"
    cost = 10

    def on_battle_start(self, game):
        pass

    def on_round_start(self, game):
        pass

    def modify_player_total(self, game, total):
        return total

    def damage_on_win(self, game, base_damage, player_total):
        return base_damage

    def on_win(self, game):
        pass

    def on_loss(self, game):
        pass


class Softener(Joker):
    name = "Softener"
    desc = "Once/round: first bust is softened (-10 total)."
    cost = 35

    def on_round_start(self, game):
        game.flags["softener_used"] = False

    def modify_player_total(self, game, total):
        if total > 21 and not game.flags.get("softener_used", False):
            game.flags["softener_used"] = True
            return total - 10
        return total


class DealerPeek(Joker):
    name = "Dealer Peek"
    desc = "Press P once/round to reveal dealer's hidden card."
    cost = 30

    def on_round_start(self, game):
        game.flags["peek_used"] = False


class LuckySeven(Joker):
    name = "Lucky Seven"
    desc = "On WIN: if your final hand has a 7, +1 damage."
    cost = 25

    def damage_on_win(self, game, base_damage, player_total):
        if any(c.rank == "7" for c in game.player_hand):
            return base_damage + 1
        return base_damage


class DoubleDownStand(Joker):
    name = "Double Down"
    desc = "Stand on 9/10/11 and WIN: +1 damage."
    cost = 40

    def on_round_start(self, game):
        game.flags["double_down_ready"] = False

    def on_player_stand(self, game):
        total = game.get_player_total()
        if total in (9, 10, 11):
            game.flags["double_down_ready"] = True

    def damage_on_win(self, game, base_damage, player_total):
        if game.flags.get("double_down_ready", False):
            return base_damage + 1
        return base_damage


class Vampire(Joker):
    name = "Vampire"
    desc = "Once/battle on WIN: heal +1 heart."
    cost = 45

    def on_battle_start(self, game):
        game.flags["vampire_used"] = False

    def on_win(self, game):
        if not game.flags.get("vampire_used", False):
            game.flags["vampire_used"] = True
            if game.player_hp < game.player_hp_max:
                game.player_hp += 1
                game.message = game.message + "  [Vampire +1]"


JOKER_POOL = [Softener, DealerPeek, LuckySeven, DoubleDownStand, Vampire]


# =============================
# Game
# =============================
class Game:
    def __init__(self):
        self.deck = Deck(num_decks=2)

        # Economy: start with enough for 1–2 cards
        self.chips = 60

        # Jokers
        self.jokers = []
        self.shop_offers = []
        self.selected_shop_index = 0

        # Battle HP
        self.player_hp_max = 5
        self.player_hp = self.player_hp_max
        self.enemy_hp_max = 3
        self.enemy_hp = 3
        self.boss_level = 1

        # Hands
        self.player_hand = []
        self.dealer_hand = []

        # State
        self.state = "PLAY"   # PLAY, DEALER, ROUND_OVER, SHOP, GAME_OVER
        self.prev_state = "PLAY"  # for closing shop
        self.message = ""
        self.flags = {}

        # Big center flash text
        self.flash_text = ""
        self.flash_until_ms = 0

        self.start_new_battle()

    def start_new_battle(self):
        self.enemy_hp_max = random.randint(3, 5)
        self.enemy_hp = self.enemy_hp_max
        self.flags = {}
        for j in self.jokers:
            j.on_battle_start(self)
        self.message = f"Boss {self.boss_level}! Win hands to deal damage."
        self.start_new_round()

    def start_new_round(self):
        self.player_hand = [self.deck.draw(), self.deck.draw()]
        self.dealer_hand = [self.deck.draw(), self.deck.draw()]
        self.state = "PLAY"
        self.flags["reveal_dealer"] = False
        self.flags["peek_used"] = False
        self.flags["double_down_ready"] = False

        for j in self.jokers:
            j.on_round_start(self)

        if self.player_hp <= 0:
            self.state = "GAME_OVER"
            self.message = "GAME OVER. Press R to restart."

    def get_player_total(self):
        total = hand_value(self.player_hand)
        for j in self.jokers:
            total = j.modify_player_total(self, total)
        return total

    def set_flash(self, text):
        self.flash_text = text
        self.flash_until_ms = pygame.time.get_ticks() + FLASH_DURATION_MS

    def flash_active(self):
        return pygame.time.get_ticks() < self.flash_until_ms

    def player_hit(self):
        if self.state != "PLAY":
            return
        self.player_hand.append(self.deck.draw())
        if self.get_player_total() > 21:
            self.end_round("lose")

    def player_stand(self):
        if self.state != "PLAY":
            return
        for j in self.jokers:
            if isinstance(j, DoubleDownStand):
                j.on_player_stand(self)
        self.state = "DEALER"
        self.message = "Dealer playing..."

    def dealer_play_step(self):
        if self.state != "DEALER":
            return
        if hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.draw())
        else:
            self.resolve_round()

    def resolve_round(self):
        p = self.get_player_total()
        d = hand_value(self.dealer_hand)

        if p > 21:
            self.end_round("lose")
            return

        if d > 21 or p > d:
            self.end_round("win")
        elif p < d:
            self.end_round("lose")
        else:
            self.end_round("push")

    def end_round(self, outcome):
        self.flags["reveal_dealer"] = True
        self.state = "ROUND_OVER"

        if outcome == "win":
            self.set_flash("YOU WIN")
            dmg = 1
            ptotal = self.get_player_total()
            for j in self.jokers:
                dmg = j.damage_on_win(self, dmg, ptotal)
            self.enemy_hp -= dmg
            self.message = f"Dealt {dmg} damage. SPACE=Continue"
            for j in self.jokers:
                j.on_win(self)

            if self.enemy_hp <= 0:
                reward = 20 + (self.boss_level - 1) * 10
                self.chips += reward
                self.message = f"BOSS DOWN! +{reward} chips. SPACE=Next boss"

        elif outcome == "lose":
            self.set_flash("YOU LOSE")
            self.player_hp -= 1
            self.message = "Took 1 damage. SPACE=Continue"
            for j in self.jokers:
                j.on_loss(self)
            if self.player_hp <= 0:
                self.state = "GAME_OVER"
                self.message = "GAME OVER. Press R to restart."
        else:
            self.set_flash("PUSH")
            self.message = "No damage. SPACE=Continue"

    def continue_after_round(self):
        if self.state != "ROUND_OVER":
            return

        if self.enemy_hp <= 0:
            self.boss_level += 1
            self.start_new_battle()
            return

        self.start_new_round()

    # ---- Shop always accessible ----
    def open_shop(self):
        if self.state == "SHOP":
            return
        self.prev_state = self.state
        self.state = "SHOP"
        self.message = "SHOP: 1-4 select, B buy, T/ESC close"
        self.shop_offers = [random.choice(JOKER_POOL)() for _ in range(4)]
        self.selected_shop_index = 0

    def close_shop(self):
        if self.state != "SHOP":
            return
        self.state = self.prev_state
        # keep message sane
        if self.state == "PLAY":
            self.message = "H=Hit  S=Stand  SPACE=...  (T=Shop)"
        elif self.state == "ROUND_OVER":
            self.message = "SPACE=Continue  (T=Shop)"

    def buy_selected(self):
        if self.state != "SHOP":
            return
        offer = self.shop_offers[self.selected_shop_index]
        if self.chips >= offer.cost:
            self.chips -= offer.cost
            self.jokers.append(offer)
            self.message = f"Bought {offer.name}! (T/ESC close)"
        else:
            self.message = "Not enough chips."

    def toggle_peek(self):
        if self.state not in ("PLAY", "DEALER"):
            return
        has_peek = any(isinstance(j, DealerPeek) for j in self.jokers)
        if not has_peek:
            return
        if not self.flags.get("peek_used", False):
            self.flags["peek_used"] = True
            self.flags["reveal_dealer"] = True
            self.message = "Peek used!"

    def restart(self):
        self.__init__()


# =============================
# Drawing helpers
# =============================
def draw_text(surf, font, text, x, y, color="fg", center=False):
    img = font.render(text, True, PALETTE[color])
    if center:
        rect = img.get_rect(center=(x, y))
        surf.blit(img, rect.topleft)
    else:
        surf.blit(img, (x, y))


def draw_box(surf, rect, border="fg"):
    pygame.draw.rect(surf, PALETTE["bg"], rect)
    pygame.draw.rect(surf, PALETTE[border], rect, 1)


def draw_card(surf, font, card, x, y, face_up=True):
    rect = pygame.Rect(x, y, CARD_W, CARD_H)
    draw_box(surf, rect, border="fg")

    if face_up:
        draw_text(surf, font, f"{card.rank}{card.suit}", x + 5, y + 4, "fg")
        pygame.draw.line(surf, PALETTE["mid"], (x + 4, y + 22), (x + CARD_W - 5, y + 22), 1)
    else:
        for yy in range(y + 12, y + CARD_H - 10, 9):
            pygame.draw.line(surf, PALETTE["mid"], (x + 6, yy), (x + CARD_W - 7, yy), 1)


def centered_hand_x(num_cards):
    total_w = num_cards * CARD_W + (num_cards - 1) * CARD_GAP
    return (VIRTUAL_W - total_w) // 2


def draw_heart(surf, x, y, size=6, filled=True):
    # monochrome tiny heart
    c = PALETTE["fg"] if filled else PALETTE["dim"]

    pygame.draw.rect(surf, c, (x, y, size, size))
    pygame.draw.rect(surf, c, (x + size, y, size, size))
    pygame.draw.rect(surf, c, (x - 1, y + size, size * 2 + 2, size))
    pygame.draw.rect(surf, c, (x + size // 2, y + size * 2, size, size))
    pygame.draw.rect(surf, c, (x + size // 2, y + size * 3, size, size))


def draw_hearts_row(surf, x, y, hp, hp_max, label):
    draw_text(surf, pygame.font.Font(None, 20), label, x, y - 14, "mid")
    for i in range(hp_max):
        draw_heart(surf, x + i * 18, y, size=6, filled=(i < hp))


def draw_enemy_face_friendly(surf, x, y):
    pygame.draw.circle(surf, PALETTE["fg"], (x, y), 18, 1)
    pygame.draw.circle(surf, PALETTE["fg"], (x - 14, y - 10), 6, 1)
    pygame.draw.circle(surf, PALETTE["fg"], (x + 14, y - 10), 6, 1)
    pygame.draw.circle(surf, PALETTE["fg"], (x - 6, y - 2), 2, 0)
    pygame.draw.circle(surf, PALETTE["fg"], (x + 6, y - 2), 2, 0)
    pygame.draw.arc(surf, PALETTE["fg"], pygame.Rect(x - 7, y + 2, 14, 10), 3.6, 5.8, 1)


# =============================
# Render
# =============================
def render(virtual, font, small, big, game: Game):
    virtual.fill(PALETTE["bg"])

    # ---- Enemy / Dealer (top) ----
    draw_text(virtual, small, f"ENEMY (Boss {game.boss_level})", MARGIN, MARGIN, "fg")

    reveal = game.flags.get("reveal_dealer", False) or game.state in ("ROUND_OVER", "SHOP", "GAME_OVER")
    dx = centered_hand_x(len(game.dealer_hand))
    dy = MARGIN + 18

    draw_enemy_face_friendly(virtual, VIRTUAL_W - MARGIN - 26, dy + 30)

    for i, c in enumerate(game.dealer_hand):
        face_up = True
        if i == 1 and not reveal and game.state in ("PLAY", "DEALER"):
            face_up = False
        draw_card(virtual, small, c, dx + i * (CARD_W + CARD_GAP), dy, face_up)

    dealer_total_text = f"TOTAL: {hand_value(game.dealer_hand)}" if reveal else "TOTAL: ?"
    draw_text(virtual, small, dealer_total_text, VIRTUAL_W - MARGIN - 130, MARGIN, "mid")

    draw_hearts_row(virtual, MARGIN, 56, game.enemy_hp, game.enemy_hp_max, "ENEMY HP")

    # ---- Player area (center) ----
    play_area_top = 110
    play_area = pygame.Rect(MARGIN, play_area_top, VIRTUAL_W - 2 * MARGIN, 96)
    draw_box(virtual, play_area, border="fg")

    draw_text(virtual, small, "YOU", play_area.x + 10, play_area.y + 8, "fg")

    px = centered_hand_x(len(game.player_hand))
    py = play_area.y + 22
    for i, c in enumerate(game.player_hand):
        draw_card(virtual, small, c, px + i * (CARD_W + CARD_GAP), py, True)

    draw_text(virtual, small, f"TOTAL: {game.get_player_total()}",
              play_area.x + play_area.w - 120, play_area.y + 8, "fg")

    draw_hearts_row(virtual, MARGIN, play_area.y + play_area.h - 30,
                    game.player_hp, game.player_hp_max, "YOUR HP")

    # ---- HUD (bottom) ----
    hud_y = VIRTUAL_H - HUD_H
    pygame.draw.line(virtual, PALETTE["fg"], (0, hud_y), (VIRTUAL_W, hud_y), 1)

    draw_text(virtual, small, "T=SHOP", MARGIN, hud_y + 10, "mid")
    draw_text(virtual, small, f"CHIPS: {game.chips}", MARGIN, hud_y + 28, "fg")

    controls = "H Hit  S Stand  P Peek  SPACE Continue"
    draw_text(virtual, small, controls, 160, hud_y + 10, "mid")

    msg_box = pygame.Rect(160, hud_y + 28, VIRTUAL_W - 160 - MARGIN, 22)
    draw_box(virtual, msg_box, border="fg")
    draw_text(virtual, small, game.message[:52], msg_box.x + 8, msg_box.y + 4, "fg")

    # ---- Big flash text ----
    if game.flash_active() and game.state != "SHOP":
        # Centered over the play area (like a dramatic result)
        draw_text(virtual, big, game.flash_text, VIRTUAL_W // 2, 155, "fg", center=True)

    # ---- Shop overlay ----
    if game.state == "SHOP":
        overlay = pygame.Rect(60, 52, 360, 170)
        draw_box(virtual, overlay, border="fg")
        draw_text(virtual, font, "SHOP", overlay.x + 12, overlay.y + 10, "fg")
        draw_text(virtual, small, f"Chips: {game.chips}", overlay.x + 240, overlay.y + 16, "mid")

        for i, offer in enumerate(game.shop_offers):
            yy = overlay.y + 48 + i * 24
            marker = ">" if i == game.selected_shop_index else " "
            color = "fg" if i == game.selected_shop_index else "mid"
            draw_text(virtual, small, f"{marker} {i+1}. {offer.name}  ${offer.cost}", overlay.x + 14, yy, color)

        sel = game.shop_offers[game.selected_shop_index]
        draw_text(virtual, small, sel.desc[:52], overlay.x + 14, overlay.y + 148, "fg")

        draw_text(virtual, small, "B buy   T/ESC close", overlay.x + 12, overlay.y + 10 + 130, "mid")


# =============================
# Main
# =============================
def main():
    pygame.init()
    pygame.display.set_caption("Blackjack Boss Battle (Shop Anytime + YOU LOSE)")

    screen = pygame.display.set_mode((WINDOW_W, WINDOW_H))
    virtual = pygame.Surface((VIRTUAL_W, VIRTUAL_H))
    clock = pygame.time.Clock()

    font = pygame.font.Font(None, 28)
    small = pygame.font.Font(None, 20)
    big = pygame.font.Font(None, 64)

    game = Game()

    while True:
        clock.tick(FPS)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game.state == "SHOP":
                        game.close_shop()
                        continue
                    pygame.quit()
                    sys.exit()

                if game.state == "GAME_OVER":
                    if event.key == pygame.K_r:
                        game.restart()
                    continue

                # Toggle shop anytime
                if event.key == pygame.K_t:
                    if game.state == "SHOP":
                        game.close_shop()
                    else:
                        game.open_shop()
                    continue

                # While in shop, only shop controls
                if game.state == "SHOP":
                    if pygame.K_1 <= event.key <= pygame.K_4:
                        game.selected_shop_index = event.key - pygame.K_1
                    elif event.key == pygame.K_b:
                        game.buy_selected()
                    continue

                # Peek
                if event.key == pygame.K_p:
                    game.toggle_peek()

                # Play controls
                if game.state == "PLAY":
                    if event.key == pygame.K_h:
                        game.player_hit()
                    elif event.key == pygame.K_s:
                        game.player_stand()

                elif game.state == "ROUND_OVER":
                    if event.key == pygame.K_SPACE:
                        game.continue_after_round()

        if game.state == "DEALER":
            game.dealer_play_step()

        render(virtual, font, small, big, game)

        pygame.transform.scale(virtual, (WINDOW_W, WINDOW_H), screen)
        pygame.display.flip()


if __name__ == "__main__":
    main()