#!/usr/bin/env python

import socket
import sys
import time
from pokereval.card import Card
from pokereval.hand_evaluator import HandEvaluator


class Player:

    msg_key = {'seat', 'blind', 'hold', 'inquire', 'flop', 'turn', 'river', 'showdown', 'pot-win', 'notify'}
    colors = {"SPADES": 1, "HEARTS": 2, "CLUBS": 3, "DIAMONDS": 4}
    points = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14}

    card_array = \
        [[0.85, 0.76, 0.66, 0.65, 0.65, 0.63, 0.62, 0.61, 0.60, 0.60, 0.59, 0.58, 0.57],
         [0.65, 0.82, 0.63, 0.63, 0.62, 0.60, 0.58, 0.58, 0.57, 0.56, 0.55, 0.54, 0.53],
         [0.64, 0.61, 0.80, 0.60, 0.59, 0.58, 0.56, 0.54, 0.54, 0.53, 0.52, 0.51, 0.50],
         [0.64, 0.61, 0.58, 0.77, 0.58, 0.56, 0.54, 0.52, 0.51, 0.50, 0.49, 0.48, 0.47],
         [0.63, 0.59, 0.57, 0.55, 0.75, 0.54, 0.52, 0.51, 0.49, 0.47, 0.47, 0.46, 0.45],
         [0.61, 0.58, 0.55, 0.53, 0.52, 0.72, 0.51, 0.49, 0.47, 0.46, 0.44, 0.43, 0.42],
         [0.60, 0.56, 0.54, 0.51, 0.50, 0.48, 0.69, 0.48, 0.46, 0.45, 0.43, 0.41, 0.40],
         [0.59, 0.55, 0.52, 0.50, 0.48, 0.46, 0.45, 0.66, 0.45, 0.44, 0.42, 0.40, 0.38],
         [0.58, 0.54, 0.51, 0.48, 0.46, 0.44, 0.43, 0.42, 0.63, 0.43, 0.41, 0.40, 0.38],
         [0.58, 0.53, 0.50, 0.47, 0.44, 0.43, 0.41, 0.41, 0.40, 0.60, 0.41, 0.40, 0.38],
         [0.57, 0.52, 0.49, 0.46, 0.44, 0.41, 0.39, 0.39, 0.38, 0.38, 0.57, 0.39, 0.37],
         [0.56, 0.51, 0.48, 0.45, 0.43, 0.40, 0.37, 0.37, 0.36, 0.36, 0.35, 0.54, 0.36],
         [0.55, 0.51, 0.47, 0.44, 0.42, 0.39, 0.37, 0.35, 0.34, 0.34, 0.33, 0.32, 0.50]]
    card_array_map = {'A': 0, 'K': 1, 'Q': 2, 'J': 3, '10': 4, '9': 5, '8': 6, '7': 7, '6': 8, '5': 9, '4': 10, '3': 11, '2': 12}

    def __init__(self, server_host, server_port, host, port, pid):
        self.cache_msg = ""
        self.server_address = (server_host, int(server_port))
        self.local_address = (host, int(port))
        self.pid = int(pid)
        self.pname = 'paji'
        self.s = None

        # public information
        self.outer_bet = 0
        self.pot = 0
        self.cards = []
        self.flops = []
        self.seats = []
        self.pos = dict()
        self.actions = dict()
        self.enemy = set()

        self.score = 0
        self.evaluate_flag = False

        # debug
        self.round = 0

        # param
        self.flop_line = 0.7
        self.raise_line = 0.98
        self.call_line1 = 0.8
        self.call_line2 = 0.89
        self.call_line3 = 0.95
        self.a = 0.2
        self.b = 0.4
        self.c = 0.6
        self.d = 0.8

    def send(self, msg):
        cnt = 0
        while True:
            try:
                self.s.sendall(msg)
            except socket.error:
                cnt += 1
                if cnt > 50:
                    return
                time.sleep(0.01)
                continue
            return

    def run(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.s.bind(self.local_address)

        while True:
            try:
                self.s.connect(self.server_address)
            except socket.error:
                time.sleep(0.1)
                continue
            break

        # register
        self.send('reg: {0} {1} \n'.format(self.pid, self.pname))

        cache_msg = ''
        over_flag = False
        flag = None
        single_msg = []
        while True:
            if over_flag:
                break
            cache_msg = (cache_msg + self.s.recv(10240)).strip()

            for line in cache_msg.split('\n'):
                line = line.strip('/ \n')
                if not line:
                    continue
                if line == 'game-over':
                    over_flag = True
                    break
                elif line in self.msg_key:
                    if flag:
                        method = getattr(self, 'handle_' + line.replace('-', '_'))
                        method(single_msg)
                        flag = None
                        single_msg = []
                    else:
                        flag = line
                else:
                    single_msg.append(line)
            cache_msg = ''
        self.s.shutdown(socket.SHUT_RDWR)
        self.s.close()

    def handle_seat(self, msg):
        for line in msg:
            seat = dict()
            seqs = line.split(':')[-1].split()
            seat['pid'] = int(seqs[0])
            seat['jetton'] = int(seqs[1])
            seat['money'] = int(seqs[2])
            seat['bet'] = 0
            self.pos[seat['pid']] = len(self.seats)
            self.seats.append(seat)
            if seat['pid'] not in self.actions:
                self.actions[seat['pid']] = {'total': 0, 'all_in': 0, 'raise': 0, 'call': 0, 'fold': 0, 'check': 0}
            # self.enemy.add(seat['pid'])
        self.round += 1
        # print('round ', self.round)

    def handle_blind(self, msg):
        for line in msg:
            pid, bet = map(int, line.split(': '))
            self.seats[self.pos[pid]]['bet'] = bet
            self.seats[self.pos[pid]]['jetton'] -= bet

    def handle_hold(self, msg):
        for line in msg:
            self.cards.append(tuple(line.split()))
        self.evaluate_flag = False

    def handle_inquire(self, msg):
        self.enemy = set()
        for line in msg[:-1]:
            seqs = line.split()
            pid, jetton, money, bet = map(int, seqs[:4])
            action = seqs[4]
            self.seats[self.pos[pid]]['jetton'] = jetton
            self.seats[self.pos[pid]]['money'] = money
            self.seats[self.pos[pid]]['bet'] = bet
            self.seats[self.pos[pid]]['action'] = action
            self.outer_bet = max(self.outer_bet, bet)

            if action in {'all_in', 'raise', 'call', 'fold', 'check'}:
                self.actions[pid][action] += 1
                self.actions[pid]['total'] += 1

            # if action == 'fold' and pid in self.enemy:
            #     self.enemy.remove(pid)
            if action in {'raise', 'call', 'all_in'}:
                self.enemy.add(pid)
        self.pot = int(msg[-1].split()[-1])
        self.action()

    def handle_flop(self, msg):
        for line in msg:
            self.flops.append(tuple(line.split()))
        self.evaluate_flag = False

    def handle_turn(self, msg):
        self.flops.append(tuple(msg[0].split()))
        self.evaluate_flag = False

    def handle_river(self, msg):
        self.flops.append(tuple(msg[0].split()))
        self.evaluate_flag = False

    def handle_showdown(self, msg):
        pass

    def handle_pot_win(self, msg):
        # pass
        self.clear()

    def handle_notify(self, msg):
        for line in msg[:-1]:
            seqs = line.split()
            # print(line)
            pid, jetton, money, bet = map(int, seqs[:4])
            action = seqs[4]
            if action in {'all_in', 'raise', 'call', 'fold', 'check'}:
                self.actions[pid][action] += 1
                self.actions[pid]['total'] += 1
            #
            # if action == 'fold' and pid in self.enemy:
            #     self.enemy.remove(pid)

    def clear(self):
        self.cards = []
        self.flops = []
        self.seats = []
        self.pos.clear()
        self.pot = 0
        self.outer_bet = 0
        self.evaluate_flag = False

    def evaluate(self):
        # if self.evaluate_flag:
        #     return self.score
        hole = [Card(self.points[p], self.colors[c]) for c, p in self.cards]
        board = [Card(self.points[p], self.colors[c]) for c, p in self.flops]
        score = HandEvaluator.evaluate_hand(hole, board)
        self.evaluate_flag = True
        # print(score)
        return score

    def evaluate_two(self):
        cx = self.card_array_map[self.cards[0][1]]
        cy = self.card_array_map[self.cards[1][1]]
        print(cx, cy)
        if cx < cy:
            cx, cy = cy, cx
        if self.cards[0][0] == self.cards[1][0]:
            cx, cy = cy, cx
        return self.card_array[cx][cy]

    def get_madness(self):
        madness = set()
        for k, v in self.actions.items():
            if v['total'] >= 10 and (v['all_in'] + v['raise'] + v['call']) / v['total'] >= 0.95:
                madness.add(k)
        return madness

    def is_rich(self):
        # own money is bigger than big blind
        if self.seats[self.pos[self.pid]]['money'] > 40:
            return True
        for pid in self.enemy:
            if self.seats[self.pos[pid]]['jetton'] > self.seats[self.pos[self.pid]]['jetton'] - 40:
                return False
        return True

    def action_two(self):
        score = self.evaluate_two()
        bet = self.seats[self.pos[self.pid]]['bet']
        call_bet = self.outer_bet - bet
        jetton = self.seats[self.pos[self.pid]]['jetton']
        money = self.seats[self.pos[self.pid]]['money']
        all_mad = self.enemy.issubset(self.get_madness())

        if score >= 0.74:  # raise_line:
            if bet < 0.5 * (money + jetton):
                self.send('raise {0} \n'.format(int(0.1 * jetton)))
            else:
                self.send('check \n')
        else:
            if self.seats[self.pos[self.pid]]['bet'] >= self.outer_bet:
                self.send('check \n')
                return
            # deal with mad bot
            if all_mad:
                # print('they are all mad')
                if score >= 0.64:
                    self.send('call \n')
                elif score >= 0.61 and self.is_rich():
                    self.send('call \n')
                else:
                    self.send('fold \n')
                return
            # ideal
            if score >= 0.64:  # call line
                if call_bet < 0.8 * (jetton + money):
                    self.send('call \n')
                else:
                    self.send('fold \n')
                return
            if score >= 0.61:
                if call_bet < 0.5 * (jetton + money):
                    self.send('call \n')
                else:
                    self.send('fold \n')
                return
            self.send('fold \n')

    # def action_two(self):
    #     score = self.evaluate()
    #     call_bet = self.outer_bet - self.seats[self.pos[self.pid]]['bet']
    #     jetton = self.seats[self.pos[self.pid]]['jetton']
    #
    #     # all_mad = len(self.enemy) > 0 and self.enemy.issubset(self.get_madness())
    #     all_mad = self.enemy.issubset(self.get_madness())
    #     # print('madness', self.get_madness())
    #     # print('alive', self.enemy)
    #
    #     if score > self.raise_line:
    #         self.send('raise {0} \n'.format(int(0.1 * self.seats[self.pos[self.pid]]['jetton'])))
    #     elif score > self.flop_line:
    #         # do check whenever can check
    #         if self.seats[self.pos[self.pid]]['bet'] >= self.outer_bet:
    #             self.send('check \n')
    #             # print('check')
    #             return
    #         # deal with situation where all opposite players are madness
    #         if all_mad:
    #             # print('they are all mad')
    #             if score >= self.call_line2 and self.is_rich():
    #                 self.send('call \n')
    #             else:
    #                 self.send('fold \n')
    #         elif score > self.call_line3:
    #             if call_bet <= jetton * self.d:
    #                 self.send('call \n')
    #             else:
    #                 self.send('fold \n')
    #         elif score > self.call_line2:
    #             if call_bet <= jetton * self.c:
    #                 self.send('call \n')
    #             else:
    #                 self.send('fold \n')
    #         elif score > self.call_line1:
    #             if call_bet <= jetton * self.b:
    #                 self.send('call \n')
    #             else:
    #                 self.send('fold \n')
    #         else:
    #             if call_bet <= jetton * self.a:
    #                 self.send('call \n')
    #             else:
    #                 self.send('fold \n')
    #     else:
    #         self.send('fold \n')

    def action_other(self):
        score = self.evaluate()
        call_bet = self.outer_bet - self.seats[self.pos[self.pid]]['bet']
        jetton = self.seats[self.pos[self.pid]]['jetton']
        if self.seats[self.pos[self.pid]]['bet'] >= self.outer_bet:
            self.send('check \n')
            return
        if score >= 0.85:
            self.send('raise {0} \n'.format(int(0.1 * jetton)))
        elif score >= 0.7:
            self.send('call \n')
        else:
            self.send('fold \n')

    def action(self):
        if len(self.flops) == 0:
            self.action_two()
        else:
            self.action_other()

def main():
    player = Player(*sys.argv[1:6])
    player.run()

if __name__ == '__main__':
    main()
