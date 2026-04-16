import tkinter as tk
from tkinter import messagebox, ttk
import copy
import random
import os
import json
from datetime import datetime
from core.standard_module import StandardModule

# --- CONSTANTES DE ESTILO FUTURISTA ---
BG_DEEP = "#0f0f1a"
BG_CARD = "#16213e"
ACCENT_CYAN = "#00d9ff"
ACCENT_CORAL = "#ff6b6b"
ACCENT_GOLD = "#ffd700"
BOARD_LIGHT = "#1a2a4a"
BOARD_DARK = "#0b1426"
TEXT_MAIN = "#ffffff"
TEXT_DIM = "#8892b0"

# --- LÓGICA DEL MOTOR DE AJEDREZ ---

class ChessEngine:
    def __init__(self):
        self.reset()

    def reset(self):
        self.board = [
            ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
            ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
            ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
        ]
        self.turn = 'w'
        self.history = [] # List of dicts with board state and move SAN
        self.castling_rights = {'w': {'K': True, 'Q': True}, 'b': {'k': True, 'q': True}}
        self.en_passant_target = None
        self.captured_w = []
        self.captured_b = []
        self.last_move = None # (r1, c1, r2, c2)

    def get_valid_moves(self, r, c):
        piece = self.board[r][c]
        if piece == '.' or (self.turn == 'w' and not piece.isupper()) or (self.turn == 'b' and not piece.islower()):
            return []
        pseudo = self.get_pseudo_moves(r, c)
        valid = []
        for m in pseudo:
            if not self.leaves_king_in_check(r, c, m[0], m[1]):
                valid.append(m)
        if piece.lower() == 'k':
            valid.extend(self.get_castling_moves(r, c))
        return valid

    def get_pseudo_moves(self, r, c):
        p = self.board[r][c].lower()
        color = 'w' if self.board[r][c].isupper() else 'b'
        m = []
        if p == 'p':
            dr = -1 if color == 'w' else 1
            if 0 <= r+dr < 8 and self.board[r+dr][c] == '.':
                m.append((r+dr, c))
                if (color == 'w' and r == 6) or (color == 'b' and r == 1):
                    if self.board[r+2*dr][c] == '.': m.append((r+2*dr, c))
            for dc in [-1, 1]:
                nc = c + dc
                if 0 <= r+dr < 8 and 0 <= nc < 8:
                    target = self.board[r+dr][nc]
                    if target != '.' and ((color == 'w' and target.islower()) or (color == 'b' and target.isupper())):
                        m.append((r+dr, nc))
                    if (r+dr, nc) == self.en_passant_target: m.append((r+dr, nc))
        elif p == 'n':
            for dr, dc in [(-2,-1), (-2,1), (-1,-2), (-1,2), (1,-2), (1,2), (2,-1), (2,1)]:
                nr, nc = r+dr, c+dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    trg = self.board[nr][nc]
                    if trg == '.' or (color == 'w' and trg.islower()) or (color == 'b' and trg.isupper()): m.append((nr, nc))
        elif p in ['b', 'r', 'q']:
            dirs = []
            if p in ['b', 'q']: dirs += [(-1,-1), (-1,1), (1,-1), (1,1)]
            if p in ['r', 'q']: dirs += [(-1,0), (1,0), (0,-1), (0,1)]
            for dr, dc in dirs:
                nr, nc = r+dr, c+dc
                while 0 <= nr < 8 and 0 <= nc < 8:
                    trg = self.board[nr][nc]
                    if trg == '.': m.append((nr, nc))
                    elif (color == 'w' and trg.islower()) or (color == 'b' and trg.isupper()):
                        m.append((nr, nc)); break
                    else: break
                    nr, nc = nr + dr, nc + dc
        elif p == 'k':
            for dr in [-1,0,1]:
                for dc in [-1,0,1]:
                    if dr==0 and dc==0: continue
                    nr, nc = r+dr, c+dc
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        trg = self.board[nr][nc]
                        if trg == '.' or (color == 'w' and trg.islower()) or (color == 'b' and trg.isupper()): m.append((nr, nc))
        return m

    def get_castling_moves(self, r, c):
        m = []
        if self.is_in_check(self.turn): return m
        rights = self.castling_rights[self.turn]
        if self.turn == 'w':
            if rights['K'] and self.board[7][5] == '.' and self.board[7][6] == '.':
                if not self.is_sq_att(7, 5, 'b') and not self.is_sq_att(7, 6, 'b'): m.append((7, 6))
            if rights['Q'] and self.board[7][1] == '.' and self.board[7][2] == '.' and self.board[7][3] == '.':
                if not self.is_sq_att(7, 3, 'b') and not self.is_sq_att(7, 2, 'b'): m.append((7, 2))
        else:
            if rights['k'] and self.board[0][5] == '.' and self.board[0][6] == '.':
                if not self.is_sq_att(0, 5, 'w') and not self.is_sq_att(0, 6, 'w'): m.append((0, 6))
            if rights['q'] and self.board[0][1] == '.' and self.board[0][2] == '.' and self.board[0][3] == '.':
                if not self.is_sq_att(0, 3, 'w') and not self.is_sq_att(0, 2, 'w'): m.append((0, 2))
        return m

    def is_sq_att(self, r, c, by_color):
        for row in range(8):
            for col in range(8):
                p = self.board[row][col]
                if p != '.' and ((by_color == 'w' and p.isupper()) or (by_color == 'b' and p.islower())):
                    if self._is_pseudo_att(row, col, r, c): return True
        return False

    def _is_pseudo_att(self, r, c, tr, tc):
        p = self.board[r][c].lower()
        dr, dc = tr - r, tc - c
        if p == 'p': return dr == (-1 if self.board[r][c].isupper() else 1) and abs(dc) == 1
        if p == 'n': return (abs(dr), abs(dc)) in [(1,2), (2,1)]
        if p == 'k': return abs(dr) <= 1 and abs(dc) <= 1
        if p in ['r', 'b', 'q']:
            if p == 'r' and dr != 0 and dc != 0: return False
            if p == 'b' and abs(dr) != abs(dc): return False
            if p == 'q' and dr != 0 and dc != 0 and abs(dr) != abs(dc): return False
            sr, sc = (0 if dr==0 else 1 if dr>0 else -1), (0 if dc==0 else 1 if dc>0 else -1)
            cr, cc = r + sr, c + sc
            while cr != tr or cc != tc:
                if self.board[cr][cc] != '.': return False
                cr, cc = cr+sr, cc+sc
            return True
        return False

    def is_in_check(self, color):
        char = 'K' if color == 'w' else 'k'
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == char: return self.is_sq_att(r, c, 'b' if color == 'w' else 'w')
        return False

    def leaves_king_in_check(self, r1, c1, r2, c2):
        orig, trg = self.board[r1][c1], self.board[r2][c2]
        self.board[r1][c1], self.board[r2][c2] = '.', orig
        check = self.is_in_check(self.turn)
        self.board[r1][c1], self.board[r2][c2] = orig, trg
        return check

    def move(self, r1, c1, r2, c2):
        p, trg = self.board[r1][c1], self.board[r2][c2]
        san = self.get_san(r1, c1, r2, c2, p, trg)
        
        # Save state for undo
        self.history.append({
            'b': [row[:] for row in self.board], 
            'r': copy.deepcopy(self.castling_rights), 
            'ep': self.en_passant_target,
            'cw': self.captured_w[:], 'cb': self.captured_b[:],
            'san': san
        })

        if trg != '.':
            if trg.isupper(): self.captured_b.append(trg)
            else: self.captured_w.append(trg)

        # Special: Castling
        if p.lower() == 'k' and abs(c2 - c1) == 2:
            if c2 == 6: self.board[r1][5], self.board[r1][7] = self.board[r1][7], '.'
            elif c2 == 2: self.board[r1][3], self.board[r1][0] = self.board[r1][0], '.'
        # Special: En Passant
        if p.lower() == 'p' and (r2, c2) == self.en_passant_target:
            self.board[r1][c2] = '.'
            if p.isupper(): self.captured_w.append('p')
            else: self.captured_b.append('P')

        self.board[r1][c1], self.board[r2][c2] = '.', p
        # Promotion
        if p == 'P' and r2 == 0: self.board[r2][c2] = 'Q'
        if p == 'p' and r2 == 7: self.board[r2][c2] = 'q'

        # Update rights
        if p == 'K': self.castling_rights['w'] = {'K': False, 'Q': False}
        if p == 'k': self.castling_rights['b'] = {'k': False, 'q': False}
        if (r1, c1) == (7, 7) or (r2, c2) == (7, 7): self.castling_rights['w']['K'] = False
        if (r1, c1) == (7, 0) or (r2, c2) == (7, 0): self.castling_rights['w']['Q'] = False
        if (r1, c1) == (0, 7) or (r2, c2) == (0, 7): self.castling_rights['b']['k'] = False
        if (r1, c1) == (0, 0) or (r2, c2) == (0, 0): self.castling_rights['b']['q'] = False

        self.en_passant_target = ((r1+r2)//2, c1) if p.lower() == 'p' and abs(r2-r1)==2 else None
        self.last_move = (r1, c1, r2, c2)
        self.turn = 'b' if self.turn == 'w' else 'w'

    def undo(self):
        if not self.history: return
        h = self.history.pop()
        self.board, self.castling_rights, self.en_passant_target = h['b'], h['r'], h['ep']
        self.captured_w, self.captured_b = h['cw'], h['cb']
        self.turn = 'b' if self.turn == 'w' else 'w'
        self.last_move = None # Simplified

    def get_san(self, r1, c1, r2, c2, p, trg):
        cols, rows = "abcdefgh", "87654321"
        pref = p.upper() if p.upper() != 'P' else ''
        capture = 'x' if trg != '.' or (p.lower() == 'p' and c1 != c2) else ''
        return f"{pref}{capture}{cols[c2]}{rows[r2]}"

    def get_all_valid_moves(self, color):
        res = []
        for r in range(8):
            for c in range(8):
                if (color == 'w' and self.board[r][c].isupper()) or (color == 'b' and self.board[r][c].islower()):
                    for m in self.get_valid_moves(r, c): res.append((r, c, m[0], m[1]))
        return res

    def get_ascii_board(self):
        ascii_str = ""
        pieces = {'K':'Rey B', 'Q':'Reina B', 'R':'Torre B', 'B':'Alfil B', 'N':'Caballo B', 'P':'Peón B',
                  'k':'Rey N', 'q':'Reina N', 'r':'Torre N', 'b':'Alfil N', 'n':'Caballo N', 'p':'Peón N', '.': '.'}
        for i, row in enumerate(self.board):
            ascii_str += str(8-i) + "  " + " | ".join([pieces[p] for p in row]) + "\n"
        ascii_str += "    a         b         c         d         e         f         g         h\n"
        return ascii_str

    def get_fen(self):
        fen_rows = []
        for row in self.board:
            empty_count = 0
            row_str = ""
            for sq in row:
                if sq == '.':
                    empty_count += 1
                else:
                    if empty_count > 0:
                        row_str += str(empty_count)
                        empty_count = 0
                    row_str += sq
            if empty_count > 0:
                row_str += str(empty_count)
            fen_rows.append(row_str)
        fen = "/".join(fen_rows)
        
        castle_str = ""
        if self.castling_rights['w']['K']: castle_str += "K"
        if self.castling_rights['w']['Q']: castle_str += "Q"
        if self.castling_rights['b']['k']: castle_str += "k"
        if self.castling_rights['b']['q']: castle_str += "q"
        if not castle_str: castle_str = "-"
        
        ep_str = "-"
        if self.en_passant_target:
            r, c = self.en_passant_target
            cols, rows = "abcdefgh", "87654321"
            ep_str = f"{cols[c]}{rows[r]}"
            
        return f"{fen} {self.turn} {castle_str} {ep_str} 0 1"

# --- INTELIGENCIA ARTIFICIAL ---

class ChessAI:
    def __init__(self, engine):
        self.engine = engine
        self.vals = {'p': 10, 'n': 32, 'b': 33, 'r': 50, 'q': 90, 'k': 20000}
        self.pst = {
            'p': [[0,0,0,0,0,0,0,0],[50,50,50,50,50,50,50,50],[10,10,20,30,30,20,10,10],[5,5,10,25,25,10,5,5],[0,0,0,20,20,0,0,0],[5,-5,-10,0,0,-10,-5,5],[5,10,10,-20,-20,10,10,5],[0,0,0,0,0,0,0,0]],
            'n': [[-50,-40,-30,-30,-30,-30,-40,-50],[-40,-20,0,0,0,0,-20,-40],[-30,0,10,15,15,10,0,-30],[-30,5,15,20,20,15,5,-30],[-30,0,15,20,20,15,0,-30],[-30,5,10,15,15,10,5,-30],[-40,-20,0,5,5,0,-20,-40],[-50,-40,-30,-30,-30,-30,-40,-50]]
        }

    def eval(self):
        s = 0
        for r in range(8):
            for c in range(8):
                piece = self.engine.board[r][c]
                if piece == '.': continue
                v = self.vals[piece.lower()]
                if piece.lower() in self.pst:
                    tr = r if piece.islower() else 7-r
                    v += self.pst[piece.lower()][tr][c]
                s += v if piece.isupper() else -v
        return s

    def minimax(self, depth, alpha, beta, maximizing):
        if depth == 0: return self.eval()
        moves = self.engine.get_all_valid_moves(self.engine.turn)
        if not moves:
            if self.engine.is_in_check(self.engine.turn): return -20000 if maximizing else 20000
            return 0
        if maximizing:
            mx = -100000
            for m in moves:
                self.engine.move(*m)
                mx = max(mx, self.minimax(depth-1, alpha, beta, False))
                self.engine.undo()
                alpha = max(alpha, mx)
                if beta <= alpha: break
            return mx
        else:
            mn = 100000
            for m in moves:
                self.engine.move(*m)
                mn = min(mn, self.minimax(depth-1, alpha, beta, True))
                self.engine.undo()
                beta = min(beta, mn)
                if beta <= alpha: break
            return mn

    def get_move(self, depth=2):
        moves = self.engine.get_all_valid_moves(self.engine.turn)
        if not moves: return None
        random.shuffle(moves)
        best, limit = None, (-100000 if self.engine.turn == 'w' else 100000)
        for m in moves:
            self.engine.move(*m)
            v = self.minimax(depth-1, -100000, 100000, self.engine.turn == 'w')
            self.engine.undo()
            if (self.engine.turn == 'w' and v > limit) or (self.engine.turn == 'b' and v < limit):
                limit, best = v, m
        return best

# --- UI COMPONENTS ---

class EvalBar(tk.Canvas):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, **kwargs)
        self.score = 0 # Positive for white, negative for black

    def update_eval(self, score):
        self.score = score
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2: return
        # Logic: 0 is center, max visual score is 1000 (10 pawns)
        max_v = 1000
        norm = max(-max_v, min(max_v, self.score))
        split = h / 2 - (norm / max_v) * (h / 2)
        
        # Glassy Eval Bar
        self.create_rectangle(0, 0, w, split, fill="#111", outline="") # Black (IA leading)
        self.create_rectangle(0, split, w, h, fill="#3a4a6a", outline="") # Blue-ish (Player leading)
        self.create_line(0, h/2, w, h/2, fill="#00d9ff", width=2)

class CapturedPieces(tk.Frame):
    def __init__(self, parent, bg, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)
        self.label = tk.Label(self, text="", bg=bg, fg=TEXT_DIM, font=("Segoe UI Symbol", 14))
        self.label.pack(side=tk.LEFT)
        self.pcs = {'K':'♔','Q':'♕','R':'♖','B':'♗','N':'♘','P':'♙','k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟'}

    def update_pieces(self, list_pcs):
        txt = "".join([self.pcs.get(p, '') for p in list_pcs])
        self.label.config(text=txt)

class ChessBoard(tk.Canvas):
    def __init__(self, parent, engine, ai, **kwargs):
        super().__init__(parent, **kwargs)
        self.engine, self.ai = engine, ai
        self.selected, self.valid = None, []
        self.difficulty = 2
        self.mode = "ia" # "ia" o "local"
        self.pcs = {'K':'♔','Q':'♕','R':'♖','B':'♗','N':'♘','P':'♙','k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟'}
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10: return
        sq = min(w, h) // 8
        ox, oy = (w-sq*8)//2, (h-sq*8)//2
        accent = "#00d9ff"
        
        for r in range(8):
            for c in range(8):
                x1, y1 = ox+c*sq, oy+r*sq
                # Usar colores más oscuros y 'glassy'
                cl = "#16213e" if (r+c)%2==0 else "#0f0f1a"
                if self.selected == (r,c): cl = "#1e3a5f"
                elif (r,c) in self.valid: cl = "#1a4a4a"
                
                # Resaltado de último movimiento
                if self.engine.last_move and (r,c) in [(self.engine.last_move[0], self.engine.last_move[1]), (self.engine.last_move[2], self.engine.last_move[3])]:
                    cl = "#223344"
                
                self.create_rectangle(x1, y1, x1+sq, y1+sq, fill=cl, outline="#1a2a4a", width=1)
                
                # Check alert
                if self.engine.is_in_check(self.engine.turn):
                    kc = 'K' if self.engine.turn == 'w' else 'k'
                    if self.engine.board[r][c] == kc:
                        self.create_oval(x1+5, y1+5, x1+sq-5, y1+sq-5, outline=ACCENT_CORAL, width=2)

                p = self.engine.board[r][c]
                if p != '.':
                    fcl = "#00d9ff" if p.isupper() else "#ff6b6b"
                    self.create_text(x1+sq/2, y1+sq/2, text=self.pcs.get(p,''), font=("Segoe UI Symbol", int(sq*0.65), "bold"), fill=fcl)
                    
                # Marcadores de Coordenadas (Modo Profesional)
                if c == 0:
                    self.create_text(x1+5, y1+5, anchor=tk.NW, text=str(8-r), font=("Courier New", max(8, int(sq*0.15)), "bold"), fill=TEXT_DIM)
                if r == 7:
                    self.create_text(x1+sq-5, y1+sq-5, anchor=tk.SE, text="abcdefgh"[c], font=("Courier New", max(8, int(sq*0.15)), "bold"), fill=TEXT_DIM)

    def _click(self, e):
        sq = min(self.winfo_width(), self.winfo_height()) // 8
        ox, oy = (self.winfo_width()-sq*8)//2, (self.winfo_height()-sq*8)//2
        c, r = (e.x-ox)//sq, (e.y-oy)//sq
        if 0<=r<8 and 0<=c<8:
            if self.selected and (r,c) in self.valid:
                self.engine.move(self.selected[0], self.selected[1], r, c)
                self.selected, self.valid = None, []
                self.master_master.update_ui()
                self.master_master.check_auto_turn()
            else:
                self.selected, self.valid = (r,c), self.engine.get_valid_moves(r,c)
            self.draw()

    def ia(self):
        if self.engine.turn == 'b':
            m = self.ai.get_move(self.difficulty)
            if m: self.engine.move(*m)
            self.master_master.update_ui()
            self.master_master.check_auto_turn()
            self._check()

    def _check(self):
        if not self.engine.get_all_valid_moves(self.engine.turn):
            res = "JAQUE MATE" if self.engine.is_in_check(self.engine.turn) else "TABLAS"
            messagebox.showinfo("ASIMOD CHESS", res)
            self.engine.reset(); self.master_master.update_ui()

# --- MÓDULO PRINCIPAL ---

class AjedrezModule(StandardModule):
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name, self.id, self.icon = "Ajedrez", "ajedrez", "♟️"
        self.engine = ChessEngine()
        self.ai = ChessAI(self.engine)
        self.game_file = os.path.join(os.path.dirname(__file__), "saved_games.json")
        self.player1_name = "Jugador 1"
        self.player2_name = "Jugador 2"
        self.asimod_thinking = False

    def render_workspace(self, parent):
        has_bg = self.style.get_background("center") is not None
        pad = 20 if has_bg else 0
        ghost_bg = self.style.get_color("bg_main")
        accent = self.style.get_color("accent")

        self.root_f = tk.Frame(parent, bg=ghost_bg)
        self.root_f.pack(fill=tk.BOTH, expand=True, padx=pad, pady=pad)

        # Header
        head = tk.Frame(self.root_f, bg=ghost_bg, pady=10)
        head.pack(fill=tk.X)
        tk.Label(head, text="♔ CHESS MASTER TACTICAL BOARD", font=("Courier New", 18, "bold"), bg=ghost_bg, fg=accent).pack()

        # Main Layout
        main_f = tk.Frame(self.root_f, bg=ghost_bg)
        main_f.pack(fill=tk.BOTH, expand=True)

        # Sidebar
        side_color = self.style.get_color("bg_sidebar")
        side = tk.Frame(main_f, bg=side_color, width=220, padx=15, pady=15)
        side.pack(side=tk.LEFT, fill=tk.Y, padx=(0, pad))
        side.pack_propagate(False)

        tk.Label(side, text="CONFIGURACIÓN", bg=side_color, fg=ACCENT_GOLD, font=("Helvetica", 9, "bold")).pack(anchor="w")
        
        # Modo de Juego
        self.mode_var = tk.StringVar(value="ia")
        
        # Player names UI
        self.players_frame = tk.Frame(side, bg=side_color)
        
        tk.Label(self.players_frame, text="JUGADOR 1 (Blancas)", bg=side_color, fg=TEXT_DIM, font=("Helvetica", 8)).pack(anchor="w", pady=(5,0))
        self.p1_entry = tk.Entry(self.players_frame, bg=ghost_bg, fg=TEXT_MAIN, bd=0, insertbackground=TEXT_MAIN)
        self.p1_entry.insert(0, self.player1_name)
        self.p1_entry.pack(fill=tk.X, pady=(0, 5))
        
        tk.Label(self.players_frame, text="JUGADOR 2 (Negras)", bg=side_color, fg=TEXT_DIM, font=("Helvetica", 8)).pack(anchor="w")
        self.p2_entry = tk.Entry(self.players_frame, bg=ghost_bg, fg=TEXT_MAIN, bd=0, insertbackground=TEXT_MAIN)
        self.p2_entry.insert(0, self.player2_name)
        self.p2_entry.pack(fill=tk.X, pady=(0, 5))

        def switch_mode():
            self.board_ui.mode = self.mode_var.get()
            if self.mode_var.get() == "local":
                self.diff_lbl.pack_forget()
                self.diff_slider.pack_forget()
                self.players_frame.pack(fill=tk.X, after=self.mode_radio2)
            else:
                self.players_frame.pack_forget()
                self.diff_lbl.pack(anchor="w", after=self.mode_radio2)
                self.diff_slider.pack(fill=tk.X, after=self.diff_lbl)
            self.reset(ask=False)

        self.mode_radio1 = tk.Radiobutton(side, text="Vs IA", variable=self.mode_var, value="ia", bg=side_color, fg=TEXT_MAIN, 
                       selectcolor=ghost_bg, activebackground=side_color, command=switch_mode)
        self.mode_radio1.pack(anchor="w", pady=2)
        self.mode_radio2 = tk.Radiobutton(side, text="Vs Jugador", variable=self.mode_var, value="local", bg=side_color, fg=TEXT_MAIN, 
                       selectcolor=ghost_bg, activebackground=side_color, command=switch_mode)
        self.mode_radio2.pack(anchor="w", pady=2)

        tk.Frame(side, bg="#333", height=1).pack(fill=tk.X, pady=10)

        self.turn_lbl = tk.Label(side, text="TURNO: BLANCAS", bg=side_color, fg=TEXT_MAIN, font=("Courier New", 11, "bold"))
        self.turn_lbl.pack(anchor="w", pady=(5, 10))

        self.diff_lbl = tk.Label(side, text="DIFICULTAD IA", bg=BG_CARD, fg=TEXT_DIM, font=("Helvetica", 9))
        self.diff_lbl.pack(anchor="w")
        self.diff_var = tk.IntVar(value=2)
        self.diff_slider = tk.Scale(side, from_=1, to=4, orient=tk.HORIZONTAL, variable=self.diff_var, bg=side_color, fg=accent, highlightthickness=0, bd=0)
        self.diff_slider.pack(fill=tk.X)

        tk.Frame(side, bg="#333", height=1).pack(fill=tk.X, pady=10)
        
        # Opciones Agente ASIMOD
        tk.Label(side, text="CONTROL ASIMOD (AGENTE)", bg=side_color, fg=ACCENT_GOLD, font=("Helvetica", 8, "bold")).pack(anchor="w")
        self.asimod_w_var = tk.BooleanVar(value=False)
        self.asimod_b_var = tk.BooleanVar(value=False)
        
        def on_agent_toggle():
            self.check_auto_turn()
            
        tk.Checkbutton(side, text="Asimod juega Blancas", variable=self.asimod_w_var, command=on_agent_toggle, bg=side_color, fg=TEXT_MAIN, selectcolor=ghost_bg, activebackground=side_color).pack(anchor="w")
        tk.Checkbutton(side, text="Asimod juega Negras", variable=self.asimod_b_var, command=on_agent_toggle, bg=side_color, fg=TEXT_MAIN, selectcolor=ghost_bg, activebackground=side_color).pack(anchor="w")
        
        # Max AI Retries Config
        retry_f = tk.Frame(side, bg=side_color)
        retry_f.pack(fill=tk.X, pady=(10, 0))
        tk.Label(retry_f, text="Fallos Máx. IA:", bg=side_color, fg=TEXT_DIM, font=("Helvetica", 8)).pack(side=tk.LEFT)
        self.ai_max_retries_var = tk.IntVar(value=5)
        tk.Spinbox(retry_f, from_=1, to=50, textvariable=self.ai_max_retries_var, width=5, bg=ghost_bg, fg=TEXT_MAIN, bd=0, buttonbackground=side_color).pack(side=tk.RIGHT)

        tk.Frame(side, bg="#333", height=1).pack(fill=tk.X, pady=10)

        tk.Frame(side, bg="#333", height=1).pack(fill=tk.X, pady=10)

        # Captured
        tk.Label(side, text="CAPTURADAS", bg=side_color, fg=TEXT_DIM, font=("Helvetica", 9)).pack(anchor="w")
        self.cap_w = CapturedPieces(side, side_color)
        self.cap_w.pack(fill=tk.X, pady=2)
        self.cap_b = CapturedPieces(side, side_color)
        self.cap_b.pack(fill=tk.X, pady=2)

        # Ghost Buttons para el módulo
        btn_style = {"bg": side_color, "fg": TEXT_MAIN, "relief": "flat", "bd": 1, "font": ("Helvetica", 10)}
        
        tk.Button(side, text="REINICIAR", command=self.reset, bg=accent, fg=self.style.get_color("bg_dark"), font=("Helvetica", 10, "bold"), bd=0, pady=10).pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        tk.Button(side, text="DESHACER", command=self.undo, cursor="hand2", **btn_style).pack(fill=tk.X, side=tk.BOTTOM, pady=5)

        # Guardar/Cargar
        tk.Frame(side, bg="#333", height=1).pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        tk.Button(side, text="CARGAR PARTIDA", command=self.load_game, cursor="hand2", **btn_style).pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        self.game_combo = ttk.Combobox(side, state="readonly")
        self.game_combo.pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        tk.Button(side, text="GUARDAR PARTIDA", command=self.save_game, cursor="hand2", bg="#2a3a5a", fg=TEXT_MAIN, relief="flat", bd=0, font=("Helvetica", 9, "bold")).pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        tk.Label(side, text="PARTIDAS", bg=side_color, fg=ACCENT_GOLD, font=("Helvetica", 9, "bold")).pack(anchor="w", side=tk.BOTTOM)

        self.update_saved_games_list()

        # Eval Bar
        self.ebar = EvalBar(main_f, bg="#000", width=12, highlightthickness=0)
        self.ebar.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=20)

        # Board
        self.board_ui = ChessBoard(main_f, self.engine, self.ai, bg=ghost_bg, highlightthickness=0)
        self.board_ui.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.board_ui.master_master = self

        # History
        hist_f = tk.Frame(main_f, bg=side_color, width=150, padx=10, pady=15)
        hist_f.pack(side=tk.LEFT, fill=tk.Y)
        hist_f.pack_propagate(False)
        tk.Label(hist_f, text="LOG", bg=side_color, fg=TEXT_DIM, font=("Helvetica", 9, "bold")).pack(anchor="w")
        self.hist_box = tk.Text(hist_f, bg=ghost_bg, fg=accent, font=("Courier New", 9), bd=0, state=tk.DISABLED)
        self.hist_box.pack(fill=tk.BOTH, expand=True, pady=5)

        self.update_ui()

    def update_ui(self):
        # Update Turn
        t_str = "BLANCAS" if self.engine.turn == 'w' else "NEGRAS"
        clr = ACCENT_CYAN if self.engine.turn == 'w' else ACCENT_CORAL
        self.turn_lbl.config(text=f"TURNO: {t_str}", fg=clr)
        
        # Update Captured
        self.cap_w.update_pieces(self.engine.captured_w)
        self.cap_b.update_pieces(self.engine.captured_b)
        
        # Update Eval
        score = self.ai.eval()
        self.ebar.update_eval(score)
        
        # Update History
        self.hist_box.config(state=tk.NORMAL)
        self.hist_box.delete("1.0", tk.END)
        for i, h in enumerate(self.engine.history):
            if i % 2 == 0: self.hist_box.insert(tk.END, f"{i//2+1}. {h['san']} ")
            else: self.hist_box.insert(tk.END, f"{h['san']}\n")
        self.hist_box.see(tk.END)
        self.hist_box.config(state=tk.DISABLED)
        
        self.board_ui.difficulty = self.diff_var.get()
        self.board_ui.draw()

    def reset(self, ask=True):
        if not ask or messagebox.askyesno("CHESS MASTER", "¿Reiniciar partida táctica?"):
            self.engine.reset()
            self.update_ui()
            self.check_auto_turn()

    def undo(self):
        self.engine.undo(); self.engine.undo()
        self.update_ui()

    def check_auto_turn(self, error_msg=None):
        if self.asimod_thinking:
            return # Ya hay un proceso de IA activo, no solapar
            
        if not self.engine.get_all_valid_moves(self.engine.turn):
            return # Game over
        
        turn = self.engine.turn
        if turn == 'w' and getattr(self, 'asimod_w_var', None) and self.asimod_w_var.get():
            self.ask_asimod_agent(turn, error_msg)
            return
        if turn == 'b' and getattr(self, 'asimod_b_var', None) and self.asimod_b_var.get():
            self.ask_asimod_agent(turn, error_msg)
            return
            
        if self.mode_var.get() == "ia" and turn == 'b':
            self.root_f.after(400, self.board_ui.ia)
            
    def ask_asimod_agent(self, turn, error_msg=None):
        color_str = "Blancas" if turn == 'w' else "Negras"
        moves = self.engine.get_all_valid_moves(turn)
        legal_mapped = []
        for m in moves:
            p, trg = self.engine.board[m[0]][m[1]], self.engine.board[m[2]][m[3]]
            cols, rows = "abcdefgh", "87654321"
            txt_m = f"{cols[m[1]]}{rows[m[0]]} {cols[m[3]]}{rows[m[2]]}"
            legal_mapped.append(txt_m)
            
        ascii_board = self.engine.get_ascii_board()
        
        sys_prompt = (
            "Eres el Gran Maestro de Ajedrez ASIMOD. Te encuentras en mitad de una partida en tiempo real. "
            "Tu único objetivo es elegir el mejor movimiento posible basándote en la posición del tablero. "
            "No posees identidad ni personalidad adicional, no eres secretaria ni asistente, eres un motor de ajedrez."
        )
        
        hist_str = ""
        for i, h in enumerate(self.engine.history):
            if i % 2 == 0: hist_str += f"{i//2+1}. {h['san']} "
            else: hist_str += f"{h['san']} "
        if not hist_str: hist_str = "Inicio del juego."
        
        fen_str = self.engine.get_fen()
        # --- DETECCIÓN TÁCTICA (AMENAZAS Y OPORTUNIDADES) ---
        threatened_pieces = []
        capture_opportunities = []
        opp_color = 'b' if turn == 'w' else 'w'
        piece_names = {'K':'Rey', 'Q':'Reina', 'R':'Torre', 'B':'Alfil', 'N':'Caballo', 'P':'Peón',
                       'k':'Rey', 'q':'Reina', 'r':'Torre', 'b':'Alfil', 'n':'Caballo', 'p':'Peón'}
        cols, rows = "abcdefgh", "87654321"
        
        for r in range(8):
            for c in range(8):
                p = self.engine.board[r][c]
                if p == '.': continue
                
                # Mis piezas bajo amenaza
                if (turn == 'w' and p.isupper()) or (turn == 'b' and p.islower()):
                    if self.engine.is_sq_att(r, c, opp_color):
                        threatened_pieces.append(f"{piece_names[p]}({cols[c]}{rows[r]})")
                
                # Piezas del rival que puedo capturar
                elif (turn == 'w' and p.islower()) or (turn == 'b' and p.isupper()):
                    if self.engine.is_sq_att(r, c, turn):
                        is_defended = self.engine.is_sq_att(r, c, opp_color)
                        status = "Defendida" if is_defended else "INDEFENSA"
                        capture_opportunities.append(f"{piece_names[p]}({cols[c]}{rows[r]}) [{status}]")
        
        history = self.engine.history
        last_move_info = "Ninguno (inicio de partida)"
        if history:
            last = history[-1]
            last_move_info = last['san']
            if last.get('captured') and last['captured'] != '.':
                cap_p = last['captured']
                cap_name = piece_names.get(cap_p, "Pieza")
                last_move_info += f" (¡CAPTURÓ tu {cap_name}!)"

        prompt = (
            f"[CONTEXTO DE AJEDREZ - Juegas con {color_str}]\n"
            f"Último movimiento rival: {last_move_info}\n"
            f"Historial PGN:\n{hist_str}\n\n"
            f"Estado FEN:\n{fen_str}\n\n"
        )
        
        if self.engine.is_in_check(turn):
            prompt += "¡ADVERTENCIA!: TU REY ESTÁ EN JAQUE. Debes elegir un movimiento que proteja a tu rey.\n\n"
        
        if threatened_pieces:
            prompt += f"[ALERTA TÁCTICA]: Tus siguientes piezas están bajo amenaza: {', '.join(threatened_pieces)}.\n"
        
        if capture_opportunities:
            prompt += f"[OPORTUNIDADES TÁCTICAS]: Puedes capturar las siguientes piezas del rival: {', '.join(capture_opportunities)}.\n"
            
        if threatened_pieces or capture_opportunities:
            prompt += "\n"
            
        prompt += (
            f"Opciones legales válidas:\n{', '.join(legal_mapped)}\n\n"
            "Elige un movimiento de la lista."
        )
        
        if error_msg:
            prompt += f"\n\n[¡ADVERTENCIA CRÍTICA!]: {error_msg}\nELIGE UNA OPCIÓN TOTALMENTE DISTINTA."
        
        prompt += (
            "\n\nDEVUELVE ÚNICAMENTE EL SIGUIENTE BLOQUE JSON RELLENO (NO agregues absolutamente nada más):\n"
            "{\n"
            '  "thought": "Breve análisis",\n'
            '  "response": "",\n'
            '  "action": "move_piece",\n'
            '  "params": "origen-destino"\n'
            "}"
        )
        
        import threading
        import asyncio
        import time
        def run_agent():
            self.asimod_thinking = True
            try:
                time.sleep(1.6) # Bypass global ASIMOD cooldown
                max_retries = self.ai_max_retries_var.get() if hasattr(self, 'ai_max_retries_var') else 5
                result = asyncio.run(self.chat_service.send_message(prompt, system_prompt=sys_prompt, silent=True, skip_tts=True, mode="AGENT", isolated=True, temperature=0.1, agent_retries=max_retries))
                
                # Watchdog: Solo reintentar si el sistema NO estaba ocupado y la IA evadió la acción
                if result.get("status") == "success" and not result.get("agent_action"):
                    self.on_voice_command("move_piece", "vacio_ilegal")
                elif result.get("status") == "busy":
                    # Si estaba ocupado, esperar un poco más y reintentar silenciosamente sin error_msg
                    time.sleep(2.0)
                    self.check_auto_turn()
            except Exception as e:
                print("[Ajedrez] Error en agente:", e)
            finally:
                self.asimod_thinking = False
                # Re-comprobar turno para dar paso al siguiente jugador (IA local o humano)
                self.root_f.after(100, self.check_auto_turn)
                
        threading.Thread(target=run_agent, daemon=True).start()

    def get_voice_commands(self): 
        return {
            "nuevo juego": "new_game",
            "reiniciar partida": "new_game", 
            "deshacer": "undo",
            "seleccionar": "select_game",
            "mover pieza": "move_piece"
        }
        
    def _load_game_by_index(self, idx):
        games = self.load_saved_games_data()
        keys = list(games.keys())
        if 0 <= idx < len(keys):
            self.game_combo.set(keys[idx])
            self.load_game()
            import winsound; winsound.MessageBeep(winsound.MB_OK)

    def on_voice_command(self, action_slug, text):
        import re
        text_lower = text.lower()
        
        if action_slug == "new_game":
            self.reset(ask=False)
            return
            
        elif action_slug == "undo":
            self.undo()
            return
            
        elif action_slug == "select_game" or (not action_slug and "seleccionar" in text_lower):
            match = re.search(r'\b(\d+)\b', text_lower)
            if match:
                idx = int(match.group(1)) - 1
                self._load_game_by_index(idx)
            else:
                self.game_combo.event_generate('<Down>')
                self._waiting_for_game_number = True
                self.chat_service.notify_system_msg("Ajedrez: Diga el número de partida...", "#888888")
            return

        if hasattr(self, '_waiting_for_game_number') and self._waiting_for_game_number:
            match = re.search(r'\b(\d+)\b', text_lower)
            if match:
                idx = int(match.group(1)) - 1
                self._load_game_by_index(idx)
                self._waiting_for_game_number = False
                return

        # Detección de movimiento por coordenadas
        if action_slug == "move_piece":
            text_lower = text_lower.replace("-", " ") # Normalizar e2-e4
            # Continúa cayendo al analizador de coordenadas existente
            
        pattern = r'\b(a|b|v|c|d|e|f|g|h|be|ve|ce|se|de|efe|ge|je|hache)\s*([1-8]|uno|un|dos|tres|cuatro|cinco|seis|siete|ocho)\b|\b([a-h])([1-8])\b'
        matches = re.findall(pattern, text_lower)
        if len(matches) >= 2:
            letter_map = {
                'a':'a', 'b':'b', 'v':'b', 'be':'b', 've':'b', 
                'c':'c', 'ce':'c', 'se':'c', 
                'd':'d', 'de':'d', 
                'e':'e', 
                'f':'f', 'efe':'f', 
                'g':'g', 'ge':'g', 'je':'g',
                'h':'h', 'hache':'h'
            }
            number_map = {
                '1':'1', 'uno':'1', 'un':'1',
                '2':'2', 'dos':'2',
                '3':'3', 'tres':'3',
                '4':'4', 'cuatro':'4',
                '5':'5', 'cinco':'5',
                '6':'6', 'seis':'6',
                '7':'7', 'siete':'7',
                '8':'8', 'ocho':'8'
            }
            parsed = []
            for m in matches:
                l = m[0] or m[2]
                n = m[1] or m[3]
                real_n = number_map[n]
                parsed.append((8 - int(real_n), ord(letter_map[l]) - ord('a')))
                
            r1, c1 = parsed[0]
            r2, c2 = parsed[1]
            
            # Chequear si es turno correcto
            if self.mode_var.get() == "ia" and self.engine.turn == 'b':
                return # Ignorar si la IA está pensando
                
            # Validar
            p = self.engine.board[r1][c1]
            correct_color = (self.engine.turn == 'w' and p.isupper()) or (self.engine.turn == 'b' and p.islower())
            
            if p != '.' and correct_color and (r2, c2) in self.engine.get_valid_moves(r1, c1):
                self.ai_retries = 0 # Reiniciar contador de fallos
                self.engine.move(r1, c1, r2, c2)
                self.update_ui()
                self.check_auto_turn()
            else:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONHAND)
                self.chat_service.notify_system_msg(f"Ajedrez: Movimiento {text_lower} no válido.", "#f54242")
                
                # Reintentar o abortar si ASIMOD está jugando
                auto_w = self.engine.turn == 'w' and getattr(self, 'asimod_w_var', None) and self.asimod_w_var.get()
                auto_b = self.engine.turn == 'b' and getattr(self, 'asimod_b_var', None) and self.asimod_b_var.get()
                if auto_w or auto_b:
                    if not hasattr(self, 'ai_retries'): self.ai_retries = 0
                    self.ai_retries += 1
                    
                    max_allowed = self.ai_max_retries_var.get() if hasattr(self, 'ai_max_retries_var') else 5
                    
                    if self.ai_retries > max_allowed:
                        self.chat_service.notify_system_msg(f"Ajedrez: ASIMOD desconectado ({self.ai_retries} fallos continuos).", "#f54242")
                        if auto_w: self.asimod_w_var.set(False)
                        if auto_b: self.asimod_b_var.set(False)
                        self.ai_retries = 0
                    else:
                        error_txt = f"PROHIBIDO REPETIR '{text_lower}'. ESE MOVIMIENTO ES INVÁLIDO. ELIGE OTRO COMPLETO DE LA LISTA."
                        self.check_auto_turn(error_msg=error_txt)
        else:
            if action_slug == "move_piece":
                import winsound
                winsound.MessageBeep(winsound.MB_ICONHAND)
                self.chat_service.notify_system_msg(f"Ajedrez: Formato incompleto '{text_lower}'.", "#f54242")
                
                auto_w = self.engine.turn == 'w' and getattr(self, 'asimod_w_var', None) and self.asimod_w_var.get()
                auto_b = self.engine.turn == 'b' and getattr(self, 'asimod_b_var', None) and self.asimod_b_var.get()
                if auto_w or auto_b:
                    if not hasattr(self, 'ai_retries'): self.ai_retries = 0
                    self.ai_retries += 1
                    max_allowed = self.ai_max_retries_var.get() if hasattr(self, 'ai_max_retries_var') else 5
                    if self.ai_retries > max_allowed:
                        self.chat_service.notify_system_msg(f"Ajedrez: ASIMOD desconectado ({self.ai_retries} fallos de formato).", "#f54242")
                        if auto_w: self.asimod_w_var.set(False)
                        if auto_b: self.asimod_b_var.set(False)
                        self.ai_retries = 0
                    else:
                        error_txt = f"FORMATO INVÁLIDO. Tu output fue '{text_lower}'. DEBES DAR EXACTAMENTE DOS COORDENADAS (origen destino), ej: 'b1 c3'."
                        self.check_auto_turn(error_msg=error_txt)
    def load_saved_games_data(self):
        if not os.path.exists(self.game_file):
            return {}
        try:
            with open(self.game_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def update_saved_games_list(self):
        games = self.load_saved_games_data()
        self.game_combo['values'] = list(games.keys())
        if games:
            self.game_combo.current(len(games)-1)

    def save_game(self):
        games = self.load_saved_games_data()
        p1 = self.p1_entry.get().strip() or "Jugador 1"
        p2 = self.p2_entry.get().strip() or "Jugador 2"
        self.player1_name, self.player2_name = p1, p2
        
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        game_id = f"{p1} vs {p2} - {date_str}"
        
        games[game_id] = {
            "p1": p1, "p2": p2,
            "mode": self.mode_var.get(),
            "board": self.engine.board,
            "turn": self.engine.turn,
            "history": self.engine.history,
            "castling": self.engine.castling_rights,
            "ep": self.engine.en_passant_target,
            "cw": self.engine.captured_w,
            "cb": self.engine.captured_b,
            "last_move": self.engine.last_move,
            "diff": self.diff_var.get()
        }
        
        with open(self.game_file, "w", encoding="utf-8") as f:
            json.dump(games, f, ensure_ascii=False, indent=2)
            
        self.update_saved_games_list()
        messagebox.showinfo("ASIMOD CHESS", "Partida guardada con éxito.")

    def load_game(self):
        game_id = self.game_combo.get()
        if not game_id: return
        games = self.load_saved_games_data()
        if game_id not in games: return
        
        g = games[game_id]
        self.mode_var.set(g.get("mode", "ia"))
        self.board_ui.mode = self.mode_var.get()
        
        self.player1_name = g.get("p1", "Jugador 1")
        self.player2_name = g.get("p2", "Jugador 2")
        self.p1_entry.delete(0, tk.END)
        self.p1_entry.insert(0, self.player1_name)
        self.p2_entry.delete(0, tk.END)
        self.p2_entry.insert(0, self.player2_name)
        
        self.diff_var.set(g.get("diff", 2))
        
        self.engine.board = copy.deepcopy(g["board"])
        self.engine.turn = g["turn"]
        self.engine.history = copy.deepcopy(g["history"])
        self.engine.castling_rights = copy.deepcopy(g["castling"])
        self.engine.en_passant_target = tuple(g["ep"]) if g["ep"] else None
        self.engine.captured_w = g["cw"][:]
        self.engine.captured_b = g["cb"][:]
        self.engine.last_move = tuple(g["last_move"]) if g["last_move"] else None
        
        self.update_ui()
        if self.mode_var.get() == "local":
            self.players_frame.pack(fill=tk.X, after=self.mode_radio2)
            self.diff_lbl.pack_forget()
            self.diff_slider.pack_forget()
        else:
            self.players_frame.pack_forget()
            self.diff_lbl.pack(anchor="w", after=self.mode_radio2)
            self.diff_slider.pack(fill=tk.X, after=self.diff_lbl)

    # --- ENDPOINTS API WEB ---
    def sync_state(self):
        try:
            games = self.load_saved_games_data()
            
            # Obtener el último p1 y p2 de la UI por si se modificaron manualmente
            p1 = self.p1_entry.get().strip() or "Jugador 1"
            p2 = self.p2_entry.get().strip() or "Jugador 2"
            
            return {
                "history_san": [h['san'] for h in self.engine.history],
                "turn": self.engine.turn,
                "mode": self.mode_var.get(),
                "player1": p1,
                "player2": p2,
                "saved_games": list(games.keys()),
                "difficulty": self.diff_var.get(),
                "is_check": self.engine.is_in_check(self.engine.turn),
                "is_game_over": not bool(self.engine.get_all_valid_moves(self.engine.turn)),
                "asimod_w": self.asimod_w_var.get(),
                "asimod_b": self.asimod_b_var.get(),
                "ai_max_retries": self.ai_max_retries_var.get()
            }
        except Exception as e:
            return {"error": str(e)}

    def sync_move(self, source, target):
        cols, rows = "abcdefgh", "87654321"
        try:
            c1, r1 = cols.index(source[0]), rows.index(source[1])
            c2, r2 = cols.index(target[0]), rows.index(target[1])
            
            valid = self.engine.get_valid_moves(r1, c1)
            if (r2, c2) in valid:
                self.engine.move(r1, c1, r2, c2)
                self.update_ui()
                
                if not self.engine.get_all_valid_moves(self.engine.turn):
                    return {"success": True, "game_over": True}
                    
                self.check_auto_turn()
                return {"success": True}
            return {"success": False, "reason": "Invalid move on backend"}
        except Exception as e:
            return {"success": False, "reason": str(e)}

    def api_save(self, p1, p2):
        self.p1_entry.delete(0, tk.END); self.p1_entry.insert(0, p1)
        self.p2_entry.delete(0, tk.END); self.p2_entry.insert(0, p2)
        self.save_game()
        return {"success": True}

    def api_load(self, game_id):
        games = self.load_saved_games_data()
        if game_id in games:
            self.game_combo.set(game_id)
            self.load_game()
            return {"success": True}
        return {"success": False}
        
    def api_reset(self, mode):
        self.mode_var.set(mode)
        if mode == "local":
            self.board_ui.mode = "local"
            self.players_frame.pack(fill=tk.X, after=self.mode_radio2)
            self.diff_lbl.pack_forget()
            self.diff_slider.pack_forget()
        else:
            self.board_ui.mode = "ia"
            self.players_frame.pack_forget()
            self.diff_lbl.pack(anchor="w", after=self.mode_radio2)
            self.diff_slider.pack(fill=tk.X, after=self.diff_lbl)
        self.reset(ask=False)
        return {"success": True}

    def api_undo(self):
        self.undo()
        return {"success": True}

    def api_update_agent_config(self, asimod_w, asimod_b, max_retries):
        self.asimod_w_var.set(asimod_w)
        self.asimod_b_var.set(asimod_b)
        if max_retries: self.ai_max_retries_var.set(int(max_retries))
        self.check_auto_turn()
        return {"success": True}

def get_module_class(): return AjedrezModule
