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
        pieces = {'K':'♔K', 'Q':'♕Q', 'R':'♖R', 'B':'♗B', 'N':'♘N', 'P':'♙P',
                  'k':'♚k', 'q':'♛q', 'r':'♜r', 'b':'♝b', 'n':'♞n', 'p':'♟p', '.': ' . '}
        for i, row in enumerate(self.board):
            ascii_str += str(8-i) + " [" + "][".join([pieces[p] for p in row]) + "]\n"
        ascii_str += "    a   b   c   d   e   f   g   h\n"
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
    def __init__(self, parent, engine, ai, style_service=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.engine, self.ai = engine, ai
        self.style = style_service
        self.selected, self.valid = None, []
        self.game_over_res = None
        self.difficulty = 2
        self.mode = "ia" # "ia" o "local"
        self.pcs = {'K':'♔','Q':'♕','R':'♖','B':'♗','N':'♘','P':'♙','k':'♚','q':'♛','r':'♜','b':'♝','n':'♞','p':'♟'}
        self.bg_photo = None
        self._bg_img_cache = None
        self._last_bg_size = (0, 0)
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", lambda e: self.draw())

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10: return
        sq = min(w, h) // 8
        ox, oy = (w-sq*8)//2, (h-sq*8)//2
        accent = "#00d9ff"
        
        # Dibujar imagen de fondo si hay estilo
        if self.style:
            bg_path = self.style.get_background("chat") or self.style.get_background("center")
            if bg_path and __import__('os').path.exists(bg_path):
                try:
                    from PIL import Image, ImageTk
                    curr_size = (w, h)
                    # Solo redimensionar si el tamaño ha cambiado o no hay caché
                    if self._bg_img_cache is None or self._last_bg_size != curr_size:
                        img_orig = Image.open(bg_path)
                        img_resized = img_orig.resize(curr_size, Image.Resampling.LANCZOS)
                        self._bg_img_cache = ImageTk.PhotoImage(img_resized)
                        self._last_bg_size = curr_size
                    
                    self.create_image(0, 0, anchor="nw", image=self._bg_img_cache)
                except Exception as e:
                    print(f"Error cargando fondo de tablero: {e}")

        for r in range(8):
            for c in range(8):
                x1, y1 = ox+c*sq, oy+r*sq
                cl = "#16213e" if (r+c)%2==0 else "#0f0f1a"
                stipple = "gray50" # Transparencia parcial para dejar ver el fondo
                
                if self.selected == (r,c): 
                    cl = "#1e3a5f"
                    stipple = "gray75"
                elif (r,c) in self.valid: 
                    cl = "#00d9ff"
                    stipple = "gray25"
                
                # Resaltado de último movimiento
                if self.engine.last_move and (r,c) in [(self.engine.last_move[0], self.engine.last_move[1]), (self.engine.last_move[2], self.engine.last_move[3])]:
                    cl = "#223344"
                    stipple = "gray75"
                
                # En Windows, stipple fusiona el color con el fondo
                self.create_rectangle(x1, y1, x1+sq, y1+sq, fill=cl, outline="#1a2a4a", width=1, stipple=stipple)
                
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

        # OVERLAY DE VICTORIA / FIN DE PARTIDA
        if self.game_over_res:
            # Fondo semi-transparente (usando stipple)
            self.create_rectangle(0, 0, w, h, fill="#000", outline="", stipple="gray50")
            # Texto principal con brillo
            self.create_text(w/2, h/2-20, text=self.game_over_res, font=("Courier New", int(sq*0.8), "bold"), fill="#fff")
            self.create_text(w/2, h/2+40, text="PARTIDA FINALIZADA", font=("Helvetica", int(sq*0.3), "bold"), fill=ACCENT_CYAN)
            self.create_text(w/2, h-40, text="HAZ CLIC PARA NUEVA PARTIDA", font=("Helvetica", 10, "italic"), fill=TEXT_DIM)

    def _click(self, e):
        sq = min(self.winfo_width(), self.winfo_height()) // 8
        ox, oy = (self.winfo_width()-sq*8)//2, (self.winfo_height()-sq*8)//2
        c, r = (e.x-ox)//sq, (e.y-oy)//sq
        if 0<=r<8 and 0<=c<8:
            if self.game_over_res:
                self.game_over_res = None
                self.engine.reset()
                self.master_master.update_ui()
                self.draw()
                return

            if self.selected and (r,c) in self.valid:
                r1, c1 = self.selected
                self.engine.move(r1, c1, r, c)
                # Locución del movimiento del oponente
                self.master_master.announce_move_voice(r1, c1, r, c)
                
                self.selected, self.valid = None, []
                self.master_master.update_ui()
                self.master_master.check_auto_turn()
            else:
                self.selected, self.valid = (r,c), self.engine.get_valid_moves(r,c)
            self.draw()

    def ia(self):
        if self.engine.turn == 'b':
            m = self.ai.get_move(self.difficulty)
            if m: 
                self.engine.move(*m)
                # Locución del movimiento de la IA Local
                if hasattr(self, 'master_master'):
                    self.master_master.announce_move_voice(*m)
                    
            self.master_master.update_ui()
            self.master_master.check_auto_turn()
            self._check()

    def _check(self):
        if not self.engine.get_all_valid_moves(self.engine.turn):
            is_check = self.engine.is_in_check(self.engine.turn)
            if is_check:
                winner = "¡GANAN BLANCAS!" if self.engine.turn == 'b' else "¡GANAN NEGRAS!"
                self.game_over_res = winner
                # Sonido de triunfo
                import winsound, threading
                def play_victory():
                    melody = [(523, 200), (659, 200), (783, 200), (1046, 600)]
                    for f, d in melody: winsound.Beep(f, d)
                threading.Thread(target=play_victory, daemon=True).start()
            else:
                self.game_over_res = "¡TABLAS!"
            
            self.draw()

# --- MÓDULO PRINCIPAL ---

class AjedrezModule(StandardModule):
    def __init__(self, chat_service, config_service, style_service, data_service=None):
        super().__init__(chat_service, config_service, style_service, data_service=data_service)
        self.name, self.id, self.icon = "Ajedrez", "ajedrez", "♟️"
        self.engine = ChessEngine()
        self.ai = ChessAI(self.engine)
        self.game_file = os.path.join(os.path.dirname(__file__), "chess_history.json")
        self.player1_name = "Jugador 1"
        self.player2_name = "Jugador 2"
        self.asimod_thinking = False
        self.agent_running = False # Lock para evitar recursión de hilos del agente
        self.ai_retries = 0
        self.last_thought = "" # Asegurar que existe para sync_state
        self.last_threats = []
        self.last_opportunities = []
        
        # Estados internos compatibles con modo headless
        self._mode = "ia"
        self._difficulty = 2
        self._asimod_w = False
        self._asimod_b = False
        self._asimod_steroids = False
        self._asimod_steroids_level = 2
        self._ai_max_retries = 5
        
        # Variables de Tkinter (se inicializan solo en render_workspace)
        self.mode_var = None
        self.diff_var = None
        self.asimod_w_var = None
        self.asimod_b_var = None
        self.asimod_steroids_var = None
        self.asimod_steroids_level_var = None
        self.ai_max_retries_var = None
        
        self.opponent_voice_id = "es-ES-AlvaroNeural" # Voz masculina seria
        self.sidebar_visible = True

    def render_workspace(self, parent):
        from ui.background_frame import BackgroundFrame
        from modules.widgets.image_button import ImageButton
        
        # Capturamos el fondo del padre para 'mimetizarnos'
        ghost_bg = parent.cget("bg")
        has_bg = self.style.get_background("center") is not None
        accent = self.style.get_color("accent")

        # Root frame del espacio de trabajo
        if has_bg:
            self.root_f = BackgroundFrame(parent, self.style, "center")
        else:
            self.root_f = tk.Frame(parent, bg=ghost_bg)
            
        self.root_f.pack(fill=tk.BOTH, expand=True)

        # Header
        if has_bg:
            head = BackgroundFrame(self.root_f, self.style, "center")
            head.config(height=45)
            head.pack_propagate(False)
        else:
            head = tk.Frame(self.root_f, bg=ghost_bg, pady=5)
            
        head.pack(fill=tk.X)
        
        # Botón para colapsar panel
        self.toggle_btn = ImageButton(head, text=" ☰ PANELES ", style=self.style, callback=self.toggle_sidebar, 
                                     font=("Helvetica", 9, "bold"), pady=5)
        self.toggle_btn.pack(side=tk.LEFT, padx=10, pady=5)
        
        tk.Label(head, text="♔ CHESS MASTER TACTICAL BOARD", font=("Courier New", 18, "bold"), bg=ghost_bg, fg=accent).pack(side=tk.LEFT, expand=True, pady=5)

        # En lugar de usar un main_f opaco que tapa el root_f, empaquetaremos directamente en root_f
        # Inicializar variables de Tkinter vinculadas a los estados internos
        self.mode_var = tk.StringVar(value=self._mode)
        self.diff_var = tk.IntVar(value=self._difficulty)
        self.asimod_w_var = tk.BooleanVar(value=self._asimod_w)
        self.asimod_b_var = tk.BooleanVar(value=self._asimod_b)
        self.asimod_steroids_var = tk.BooleanVar(value=self._asimod_steroids)
        self.asimod_steroids_level_var = tk.IntVar(value=self._asimod_steroids_level)
        self.ai_max_retries_var = tk.IntVar(value=self._ai_max_retries)

        # Sincronizar cambios de la UI hacia las variables internas
        self.mode_var.trace_add("write", lambda *a: setattr(self, "_mode", self.mode_var.get()))
        self.diff_var.trace_add("write", lambda *a: setattr(self, "_difficulty", self.diff_var.get()))
        self.asimod_w_var.trace_add("write", lambda *a: setattr(self, "_asimod_w", self.asimod_w_var.get()))
        self.asimod_b_var.trace_add("write", lambda *a: setattr(self, "_asimod_b", self.asimod_b_var.get()))
        self.asimod_steroids_var.trace_add("write", lambda *a: setattr(self, "_asimod_steroids", self.asimod_steroids_var.get()))
        self.asimod_steroids_level_var.trace_add("write", lambda *a: setattr(self, "_asimod_steroids_level", self.asimod_steroids_level_var.get()))
        self.ai_max_retries_var.trace_add("write", lambda *a: setattr(self, "_ai_max_retries", self.ai_max_retries_var.get()))

        # Sidebar textura
        side_color = self.style.get_color("bg_sidebar") if not has_bg else ghost_bg
        panel_bd = 1 if has_bg else 0
        
        if has_bg:
            self.side_panel = BackgroundFrame(self.root_f, self.style, "module_box", width=250)
            self.side_panel.config(highlightthickness=panel_bd, highlightbackground="#333")
            # Padding interno manual ya que canvas ignora padx de init
            self.side_panel._padx, self.side_panel._pady = 15, 15
        else:
            self.side_panel = tk.Frame(self.root_f, bg=side_color, width=250, padx=15, pady=15, highlightthickness=panel_bd)
            
        self.side_panel.pack(side=tk.LEFT, fill=tk.Y, padx=0)
        self.side_panel.pack_propagate(False)

        tk.Label(self.side_panel, text="CONFIGURACIÓN", bg=side_color, fg=ACCENT_GOLD, font=("Helvetica", 9, "bold")).pack(anchor="w")
        
        # Modo de Juego
        
        # Player names UI
        self.players_frame = tk.Frame(self.side_panel, bg=side_color)
        
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

        self.mode_radio1 = tk.Radiobutton(self.side_panel, text="Vs IA", variable=self.mode_var, value="ia", bg=side_color, fg=TEXT_MAIN, 
                       selectcolor=ghost_bg, activebackground=side_color, command=switch_mode)
        self.mode_radio1.pack(anchor="w", pady=2)
        self.mode_radio2 = tk.Radiobutton(self.side_panel, text="Vs Jugador", variable=self.mode_var, value="local", bg=side_color, fg=TEXT_MAIN, 
                       selectcolor=ghost_bg, activebackground=side_color, command=switch_mode)
        self.mode_radio2.pack(anchor="w", pady=2)

        tk.Frame(self.side_panel, bg="#333", height=1).pack(fill=tk.X, pady=10)

        self.turn_lbl = tk.Label(self.side_panel, text="TURNO: BLANCAS", bg=side_color, fg=TEXT_MAIN, font=("Courier New", 11, "bold"))
        self.turn_lbl.pack(anchor="w", pady=(5, 10))

        self.diff_lbl = tk.Label(self.side_panel, text="DIFICULTAD IA", bg=BG_CARD, fg=TEXT_DIM, font=("Helvetica", 9))
        self.diff_lbl.pack(anchor="w")
        self.diff_slider = tk.Scale(self.side_panel, from_=1, to=4, orient=tk.HORIZONTAL, variable=self.diff_var, bg=side_color, fg=accent, highlightthickness=0, bd=0)
        self.diff_slider.pack(fill=tk.X)

        tk.Frame(self.side_panel, bg="#333", height=1).pack(fill=tk.X, pady=10)
        
        # Opciones Agente ASIMOD
        tk.Label(self.side_panel, text="CONTROL ASIMOD (AGENTE)", bg=side_color, fg=ACCENT_GOLD, font=("Helvetica", 8, "bold")).pack(anchor="w")
        
        def on_agent_toggle():
            self.check_auto_turn()
            
        tk.Checkbutton(self.side_panel, text="Asimod juega Blancas", variable=self.asimod_w_var, command=on_agent_toggle, bg=side_color, fg=TEXT_MAIN, selectcolor=ghost_bg, activebackground=side_color).pack(anchor="w")
        tk.Checkbutton(self.side_panel, text="Asimod juega Negras", variable=self.asimod_b_var, command=on_agent_toggle, bg=side_color, fg=TEXT_MAIN, selectcolor=ghost_bg, activebackground=side_color).pack(anchor="w")
        
        # Max AI Retries Config
        retry_f = tk.Frame(self.side_panel, bg=side_color)
        retry_f.pack(fill=tk.X, pady=(10, 0))
        tk.Label(retry_f, text="Fallos Máx. IA:", bg=side_color, fg=TEXT_DIM, font=("Helvetica", 8)).pack(side=tk.LEFT)
        tk.Spinbox(retry_f, from_=1, to=50, textvariable=self.ai_max_retries_var, width=5, bg=ghost_bg, fg=TEXT_MAIN, bd=0, buttonbackground=side_color).pack(side=tk.RIGHT)

        tk.Frame(self.side_panel, bg="#333", height=1).pack(fill=tk.X, pady=10)

        # ASIMOD Esteroides
        tk.Label(self.side_panel, text="ASIMOD ESTEROIDES (TACTICAL HINT)", bg=side_color, fg=ACCENT_GOLD, font=("Helvetica", 8, "bold")).pack(anchor="w")
        tk.Checkbutton(self.side_panel, text="Activar Esteroides", variable=self.asimod_steroids_var, bg=side_color, fg=ACCENT_CYAN, selectcolor=ghost_bg, activebackground=side_color, font=("Helvetica", 8, "bold")).pack(anchor="w")
        
        steroid_f = tk.Frame(self.side_panel, bg=side_color)
        steroid_f.pack(fill=tk.X, pady=(2, 0))
        tk.Label(steroid_f, text="Nivel Táctico:", bg=side_color, fg=TEXT_DIM, font=("Helvetica", 8)).pack(side=tk.LEFT)
        self.steroid_slider = tk.Scale(steroid_f, from_=1, to=5, orient=tk.HORIZONTAL, variable=self.asimod_steroids_level_var, bg=side_color, fg=ACCENT_CYAN, highlightthickness=0, bd=0, showvalue=0, length=80)
        self.steroid_slider.pack(side=tk.RIGHT)

        tk.Frame(self.side_panel, bg="#333", height=1).pack(fill=tk.X, pady=10)


        # Captured
        tk.Label(self.side_panel, text="CAPTURADAS", bg=side_color, fg=TEXT_DIM, font=("Helvetica", 9)).pack(anchor="w")
        self.cap_w = CapturedPieces(self.side_panel, side_color)
        self.cap_w.pack(fill=tk.X, pady=2)
        self.cap_b = CapturedPieces(self.side_panel, side_color)
        self.cap_b.pack(fill=tk.X, pady=2)

        # Ghost Buttons para el módulo
        ImageButton(self.side_panel, text="REINICIAR", callback=self.reset, style=self.style, font=("Helvetica", 10, "bold"), pady=10).pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        ImageButton(self.side_panel, text="DESHACER", callback=self.undo, style=self.style, font=("Helvetica", 10)).pack(fill=tk.X, side=tk.BOTTOM, pady=5)

        # Guardar/Cargar
        tk.Frame(self.side_panel, bg="#333", height=1).pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        ImageButton(self.side_panel, text="CARGAR PARTIDA", callback=self.load_game, style=self.style, font=("Helvetica", 10)).pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        self.game_combo = ttk.Combobox(self.side_panel, state="readonly", width=18)
        self.game_combo.pack(fill=tk.X, side=tk.BOTTOM, pady=5, padx=5)
        ImageButton(self.side_panel, text="GUARDAR PARTIDA", callback=self.save_game, style=self.style, font=("Helvetica", 9, "bold")).pack(fill=tk.X, side=tk.BOTTOM, pady=5)
        tk.Label(self.side_panel, text="PARTIDAS", bg=side_color, fg=ACCENT_GOLD, font=("Helvetica", 9, "bold")).pack(anchor="w", side=tk.BOTTOM)

        self.update_saved_games_list()

        # Eval Bar
        self.ebar = EvalBar(self.root_f, bg="#000", width=12, highlightthickness=0)
        self.ebar.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=20)

        # Board
        self.board_ui = ChessBoard(self.root_f, self.engine, self.ai, style_service=self.style, bg=ghost_bg, highlightthickness=0)
        self.board_ui.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.board_ui.master_master = self

        # History
        hist_color = ghost_bg
        if has_bg:
            self.hist_f = BackgroundFrame(self.root_f, self.style, "module_box", width=150)
            self.hist_f.config(highlightthickness=panel_bd, highlightbackground="#333")
        else:
            self.hist_f = tk.Frame(self.root_f, bg=hist_color, width=150, padx=10, pady=15, highlightthickness=panel_bd)
        self.hist_f.pack(side=tk.LEFT, fill=tk.Y)
        self.hist_f.pack_propagate(False)
        tk.Label(self.hist_f, text="LOG", bg=ghost_bg, fg=TEXT_DIM, font=("Helvetica", 9, "bold")).pack(anchor="w", pady=(15,0), padx=10)
        self.hist_box = tk.Text(self.hist_f, bg=ghost_bg, fg=accent, font=("Courier New", 9), bd=0, state=tk.DISABLED)
        self.hist_box.pack(fill=tk.BOTH, expand=True, pady=5, padx=10)

        self.update_ui()

    def update_ui(self):
        """Sincroniza el estado del motor con los componentes de la interfaz."""
        # Actualizar datos tácticos globales (usados por web y escritorio)
        self._update_tactical_data()
        
        if not hasattr(self, "turn_lbl") or self.turn_lbl is None or not self.turn_lbl.winfo_exists():
            return

        # 1. Etiqueta de Turno
        p1 = self.p1_entry.get().strip() or self.player1_name
        p2 = self.p2_entry.get().strip() or self.player2_name
        
        if self.engine.turn == 'w':
            txt = f"TURNO: {p1.upper()} (Blancas)"
            cl = ACCENT_CYAN
        else:
            txt = f"TURNO: {p2.upper()} (Negras)"
            cl = ACCENT_CORAL
        
        self.turn_lbl.config(text=txt, fg=cl)

        # 2. Piezas Capturadas
        if hasattr(self, "cap_w"): self.cap_w.update_pieces(self.engine.captured_w)
        if hasattr(self, "cap_b"): self.cap_b.update_pieces(self.engine.captured_b)

        # 3. Eval Bar (Usamos el evaluador de la IA)
        if hasattr(self, "ebar"):
            score = self.ai.eval()
            self.ebar.update_eval(score)

        # 4. Historial (Text Box)
        if hasattr(self, "hist_box"):
            self.hist_box.config(state=tk.NORMAL)
            self.hist_box.delete("1.0", tk.END)
            hist_text = ""
            for i, h in enumerate(self.engine.history):
                if i % 2 == 0:
                    hist_text += f"{i//2 + 1}. {h['san']} "
                else:
                    hist_text += f"{h['san']}\n"
            self.hist_box.insert(tk.END, hist_text)
            self.hist_box.see(tk.END)
            self.hist_box.config(state=tk.DISABLED)

        # 5. Redibujar Tablero
        if hasattr(self, 'board_ui') and self.board_ui and hasattr(self.board_ui, 'winfo_exists') and self.board_ui.winfo_exists():
            self.board_ui.draw()

    def _update_tactical_data(self):
        """Calcula amenazas y oportunidades actuales para el feed táctico."""
        threats = []
        opportunities = []
        turn = self.engine.turn
        opp_color = 'b' if turn == 'w' else 'w'
        piece_names = {'K':'Rey', 'Q':'Reina', 'R':'Torre', 'B':'Alfil', 'N':'Caballo', 'P':'Peón',
                       'k':'Rey', 'q':'Reina', 'r':'Torre', 'b':'Alfil', 'n':'Caballo', 'p':'Peón'}
        cols, rows = "abcdefgh", "87654321"

        for r in range(8):
            for c in range(8):
                p = self.engine.board[r][c]
                if p == '.': continue
                
                # Mis piezas bajo amenaza directa
                if (turn == 'w' and p.isupper()) or (turn == 'b' and p.islower()):
                    if self.engine.is_sq_att(r, c, opp_color):
                        threats.append(f"{piece_names[p]}({cols[c]}{rows[r]})")
                
                # Piezas del rival que puedo capturar
                elif (turn == 'w' and p.islower()) or (turn == 'b' and p.isupper()):
                    if self.engine.is_sq_att(r, c, turn):
                        # Nota: Aquí podríamos añadir lógica de si está defendida o no
                        opportunities.append(f"{piece_names[p]}({cols[c]}{rows[r]})")
        
        self.last_threats = threats
        self.last_opportunities = opportunities


    def toggle_sidebar(self):
        pad = 20 if self.style.get_background("center") is not None else 0
        if self.sidebar_visible:
            self.side_panel.pack_forget()
            self.hist_f.pack_forget() # También ocultamos el log para máxima limpieza
            self.sidebar_visible = False
            self.toggle_btn.config(text="☰ MOSTRAR PANELES")
        else:
            self.side_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, pad), before=self.ebar)
            self.hist_f.pack(side=tk.LEFT, fill=tk.Y, after=self.board_ui)
            self.sidebar_visible = True
            self.toggle_btn.config(text="☰ OCULTAR PANELES")

        self.board_ui.difficulty = self.diff_var.get() if self.diff_var else self._difficulty
        self.board_ui.draw()

    def reset(self, ask=True):
        if not ask or messagebox.askyesno("CHESS MASTER", "¿Reiniciar partida táctica?"):
            self.engine.reset()
            self.ai_retries = 0
            self.agent_running = False
            self.asimod_thinking = False
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
        asimod_w = self.asimod_w_var.get() if self.asimod_w_var else self._asimod_w
        asimod_b = self.asimod_b_var.get() if self.asimod_b_var else self._asimod_b
        
        if turn == 'w' and asimod_w:
            self.ask_asimod_agent(turn, error_msg)
            return
        if turn == 'b' and asimod_b:
            self.ask_asimod_agent(turn, error_msg)
            return
            
        mode = self.mode_var.get() if self.mode_var else self._mode
        if mode == "ia" and turn == 'b':
            if hasattr(self, 'board_ui') and self.board_ui and self.board_ui.winfo_exists():
                self.root_f.after(400, self.board_ui.ia)
            else:
                # Simular delay de la IA en modo headless/web
                import threading
                threading.Timer(0.4, self.board_ui_ia_headless).start()

    def board_ui_ia_headless(self):
        """Ejecuta el movimiento de la IA local sin depender de widgets de tablero."""
        m = self.ai.get_move(self._difficulty)
        if m:
            self.engine.move(*m)
            self.update_ui()
            self.check_auto_turn()

    def ask_asimod_agent(self, turn, error_msg=None):
        if self.agent_running:
            print("[Ajedrez] Ignorando trigger: Ya hay un agente en ejecución.")
            return
            
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

        sys_prompt = (
            "Eres ASIMOD, el Gran Maestro de Ajedrez más avanzado. Tu pensamiento es una mezcla de táctica profunda y estrategia a largo plazo.\n"
            "INSTRUCCIONES CRÍTICAS:\n"
            "1. Analiza el tablero basándote únicamente en la posición de las piezas.\n"
            "2. Responde SIEMPRE con un objeto JSON válido.\n"
            "3. NUNCA uses notación algebraica (ej: Nf3). Usa exclusivamente coordenadas (ej: g1 f3).\n"
            "4. Tu razonamiento ('thought') debe ser profesional, técnico y ÚNICO para esta posición. Evita frases genéricas o repetitivas.\n"
            "5. NO incluyas introducciones como 'ASIMOD:' o 'Pensamiento:'."
        )

        prompt = (
            f"[SITUACIÓN ACTUAL - Juegas con {color_str}]\n"
            f"Historial de la partida: {hist_str}\n" 
            f"Último movimiento rival: {last_move_info}\n"
            f"Posición FEN: {fen_str}\n\n"
            "[TABLERO VISUAL (ASCII)]:\n"
            f"{ascii_board}\n\n"
        )
        
        if self.engine.is_in_check(turn):
            prompt += "¡URGENTE!: TU REY ESTÁ EN JAQUE. Debes moverlo o protegerlo de inmediato.\n\n"
        
        if threatened_pieces:
            prompt += f"[AMENAZAS]: Tus siguientes piezas corren peligro: {', '.join(threatened_pieces)}.\n"
        
        if capture_opportunities:
            prompt += f"[OPORTUNIDADES]: Puedes capturar: {', '.join(capture_opportunities)}.\n"
            
        self.last_threats = threatened_pieces
        self.last_opportunities = capture_opportunities
            
        if threatened_pieces or capture_opportunities:
            prompt += "\n"
            
        # --- MODO ESTEROIDES (SUGERENCIA DEL MOTOR) ---
        asimod_steroids = self.asimod_steroids_var.get() if self.asimod_steroids_var else self._asimod_steroids
        if asimod_steroids:
            try:
                # Obtenemos el mejor movimiento del motor local con la profundidad de esteroides
                depth = self.asimod_steroids_level_var.get() if self.asimod_steroids_level_var else self._asimod_steroids_level
                best_move = self.ai.get_move(depth=depth)
                if best_move:
                    r1, c1, r2, c2 = best_move
                    cols, rows = "abcdefgh", "87654321"
                    move_txt = f"{cols[c1]}{rows[r1]} {cols[c2]}{rows[r2]}"
                    prompt += f"\n[CONSEJO EXPERTO]: Considera jugar {move_txt}.\n"
            except Exception as e:
                print(f"[Ajedrez-Esteroides] Error obteniendo sugerencia: {e}")

        prompt += (
            "--- EJEMPLOS DE FORMATO ---\n"
            "Assistant: {\n"
            "  \"thought\": \"[Análisis técnico de la posición actual y plan a corto plazo]\",\n"
            "  \"action\": \"move_piece\",\n"
            "  \"params\": \"[origen] [destino]\"\n"
            "}\n\n"
            "--- TU TURNO ---\n"
            f"MOVIMIENTOS LEGALES: {', '.join(legal_mapped)}\n"
            "Responde con el JSON de 'move_piece' usando SOLO coordenadas."
        )
        
        import threading
        import asyncio
        import time
        def run_agent():
            self.agent_running = True
            self.asimod_thinking = True
            try:
                time.sleep(1.6) # Bypass global ASIMOD cooldown
                max_retries = self._ai_max_retries
                if hasattr(self, 'ai_max_retries_var') and self.ai_max_retries_var:
                    max_retries = self.ai_max_retries_var.get()
                
                result = asyncio.run(self.chat_service.send_message(prompt, system_prompt=sys_prompt, silent=True, skip_tts=True, mode="AGENT", isolated=True, temperature=0.3, agent_retries=max_retries))
                
                # Obtener pensamiento
                thought = result.get("thought", "")
                
                # Limpiar prefijos de forma agresiva
                import re
                thought = re.sub(r'(?i)^(ASIMOD|PENSAMIENTO|ANALISIS|EXAMPLE|EJEMPLO):\s*', '', thought).strip()
                thought = re.sub(r'\(?FEN:?\s*[a-zA-Z0-9/]+\s+[wb]\s+[KQkq-]+\s*[a-h0-1\-]*\s*\d*\s*\d*\)?', '', thought).strip()
                # Eliminar cualquier residuo de corchetes de ejemplo (ej: [Breve análisis...])
                thought = re.sub(r'\[.*?\]', '', thought).strip() 
                thought = re.sub(r'\s+', ' ', thought).strip()
                
                # NOTIFICACIÓN ÚNICA (Solo aquí, sin repetir el nombre del agente)
                if thought:
                    self.last_thought = thought
                    self.chat_service.notify_system_msg(thought, "#4ade80", beep=False)
                
                # Watchdog: Solo reintentar si el sistema NO estaba ocupado y la IA evadió la acción
                if result.get("status") == "success" and not result.get("agent_action"):
                    # Si no hay acción, esperamos 2 segundos antes de permitir que el loop de error actúe
                    time.sleep(1.0)
                    self.on_voice_command("move_piece", "formato_json_incorrecto")
                elif result.get("status") == "busy":
                    # Si estaba ocupado, esperar un poco más y reintentar silenciosamente sin error_msg
                    time.sleep(2.0)
                    self.check_auto_turn()
            except Exception as e:
                print("[Ajedrez] Error en agente:", e)
            finally:
                self.asimod_thinking = False
                self.agent_running = False
                # Re-comprobar turno de forma segura
                if hasattr(self, 'root_f') and self.root_f and self.root_f.winfo_exists():
                    self.root_f.after(100, self.check_auto_turn)
                else:
                    self.check_auto_turn()
                
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

        # Normalizar texto para ayudar al parser
        text_lower = text_lower.replace("x", " ").replace("-", " ").replace("+", " ").replace("#", " ")
        
        pattern = r'(?i)\b(a|b|v|c|d|e|f|g|h|be|ve|ce|se|de|efe|ge|je|hache)\s*([1-8]|uno|un|dos|tres|cuatro|cinco|seis|siete|ocho)\b|([a-h])([1-8])'
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
            # Procesar el pensamiento antes de ejecutar el movimiento
            # Para garantizar que se imprime SIEMPRE ANTES de validar o fallar.
            asimod_w = self.asimod_w_var.get() if self.asimod_w_var else self._asimod_w
            asimod_b = self.asimod_b_var.get() if self.asimod_b_var else self._asimod_b
            
            auto_w = self.engine.turn == 'w' and asimod_w
            auto_b = self.engine.turn == 'b' and asimod_b
            
            raw_thought = getattr(self.chat_service, 'current_agent_thought', "") or ""
            parsed_thought = ""
            if raw_thought and (auto_w or auto_b):
                # No notificamos aquí para evitar duplicados, 
                # pero limpiamos para la locución si es necesario
                import re
                parsed_thought = re.sub(r'^(?i)(ASIMOD:\s*)+', '', raw_thought).strip()
                parsed_thought = re.sub(r'\(?FEN:?\s*[a-zA-Z0-9/]+\s+[wb]\s+[KQkq-]+\s*[a-h0-1\-]*\s*\d*\s*\d*\)?', '', parsed_thought).strip()
                parsed_thought = re.sub(r'\s+', ' ', parsed_thought).strip()
                
            p = self.engine.board[r1][c1]
            correct_color = (self.engine.turn == 'w' and p.isupper()) or (self.engine.turn == 'b' and p.islower())
            
            # DIAGNÓSTICO:
            print(f"[Ajedrez DEBUG] Recibido: {text_lower} -> ({r1},{c1}) a ({r2},{c2})")
            print(f"[Ajedrez DEBUG] Pieza en origen: '{p}', Turno motor: '{self.engine.turn}', Color correcto: {correct_color}")
            
            if p != '.' and correct_color and (r2, c2) in self.engine.get_valid_moves(r1, c1):
                # Locución SOLO si es un agente y ha acertado el movimiento
                if parsed_thought and self.config_service.get("audio_agent", True) and getattr(self.chat_service, 'voice_service', None):
                    import threading
                    v_srv = self.chat_service.voice_service
                    # Ejecutamos la locución en un hilo independiente para que no sea destruida por el cierre del loop actual
                    threading.Thread(target=lambda: v_srv.speak_text(parsed_thought), daemon=True).start()
                    
                self.ai_retries = 0 # Reiniciar contador de fallos
                self.engine.move(r1, c1, r2, c2)
                
                # Si NO es un agente moviendo (es el humano por voz), anunciar el movimiento
                if not parsed_thought:
                    self.announce_move_voice(r1, c1, r2, c2)
                    
                self.update_ui()
                self.check_auto_turn()
            else:
                self.chat_service.notify_system_msg(f"Ajedrez: Movimiento {text_lower} no válido.", "#f54242", beep=False)
                
                # Reintentar o abortar si ASIMOD está jugando
                auto_w = self.engine.turn == 'w' and getattr(self, 'asimod_w_var', None) and self.asimod_w_var.get()
                auto_b = self.engine.turn == 'b' and getattr(self, 'asimod_b_var', None) and self.asimod_b_var.get()
                if auto_w or auto_b:
                    if not hasattr(self, 'ai_retries'): self.ai_retries = 0
                    self.ai_retries += 1
                    
                    max_allowed = self.ai_max_retries_var.get() if (hasattr(self, 'ai_max_retries_var') and self.ai_max_retries_var) else self._ai_max_retries
                    
                    if self.ai_retries > max_allowed:
                        import threading
                        def triple_beep():
                            import winsound, time
                            for _ in range(3):
                                winsound.Beep(400, 150)
                                time.sleep(0.05)
                        threading.Thread(target=triple_beep, daemon=True).start()
                        
                        self.chat_service.notify_system_msg(f"Ajedrez: ASIMOD desconectado ({self.ai_retries} fallos continuos).", "#f54242", beep=False)
                        if auto_w: self.asimod_w_var.set(False)
                        if auto_b: self.asimod_b_var.set(False)
                        self.ai_retries = 0
                    else:
                        error_txt = f"ERROR: El movimiento '{text_lower}' NO está permitido en esta posición. Revisa los MOVIMIENTOS LEGALES."
                        # Añadimos un delay más largo para romper el frenesí de errores
                        self.root_f.after(1500, lambda: self.check_auto_turn(error_msg=error_txt))
        else:
            if action_slug == "move_piece":
                auto_w = self.engine.turn == 'w' and getattr(self, 'asimod_w_var', None) and self.asimod_w_var.get()
                auto_b = self.engine.turn == 'b' and getattr(self, 'asimod_b_var', None) and self.asimod_b_var.get()
                
                # No volvemos a mostrar el pensamiento aquí

                self.chat_service.notify_system_msg(f"Ajedrez: Formato incompleto '{text_lower}'.", "#f54242", beep=False)
                
                if auto_w or auto_b:
                    if not hasattr(self, 'ai_retries'): self.ai_retries = 0
                    self.ai_retries += 1
                    max_allowed = self.ai_max_retries_var.get() if (hasattr(self, 'ai_max_retries_var') and self.ai_max_retries_var) else self._ai_max_retries
                    if self.ai_retries > max_allowed:
                        import threading
                        def triple_beep():
                            import winsound, time
                            for _ in range(3):
                                winsound.Beep(400, 150)
                                time.sleep(0.05)
                        threading.Thread(target=triple_beep, daemon=True).start()
                        
                        self.chat_service.notify_system_msg(f"Ajedrez: ASIMOD desconectado ({self.ai_retries} fallos de formato).", "#f54242", beep=False)
                        if auto_w: self.asimod_w_var.set(False)
                        if auto_b: self.asimod_b_var.set(False)
                        self.ai_retries = 0
                    else:
                        error_txt = f"FORMATO INVÁLIDO. Tu respuesta fue '{text_lower}'. Debes dar exactamente dos coordenadas (ej: 'b1 c3')."
                        # Usar root.after para permitir que el hilo actual termine y libere el lock agent_running
                        self.root_f.after(800, lambda: self.check_auto_turn(error_msg=error_txt))
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
            
            # Formatear el último movimiento como coordenadas de texto (e2 e4)
            last_move_coords = None
            if hasattr(self.engine, 'last_move') and self.engine.last_move:
                r1, c1, r2, c2 = self.engine.last_move
                cols, rows = "abcdefgh", "87654321"
                last_move_coords = f"{cols[c1]}{rows[r1]} {cols[c2]}{rows[r2]}"

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
                "asimod_w": self.asimod_w_var.get() if self.asimod_w_var else self._asimod_w,
                "asimod_b": self.asimod_b_var.get() if self.asimod_b_var else self._asimod_b,
                "asimod_steroids": self.asimod_steroids_var.get() if self.asimod_steroids_var else self._asimod_steroids,
                "steroids_level": self.asimod_steroids_level_var.get() if self.asimod_steroids_level_var else self._asimod_steroids_level,
                "ai_max_retries": self.ai_max_retries_var.get() if self.ai_max_retries_var else self._ai_max_retries,
                "last_thought": self.last_thought,
                "last_move": last_move_coords,
                "threats": getattr(self, 'last_threats', []),
                "opportunities": getattr(self, 'last_opportunities', [])
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

    def api_update_agent_config(self, asimod_w, asimod_b, max_retries, steroids=None, steroids_level=None):
        if self.asimod_w_var: self.asimod_w_var.set(asimod_w)
        else: self._asimod_w = bool(asimod_w)
        
        if self.asimod_b_var: self.asimod_b_var.set(asimod_b)
        else: self._asimod_b = bool(asimod_b)
        
        if max_retries: 
            if self.ai_max_retries_var: self.ai_max_retries_var.set(int(max_retries))
            else: self._ai_max_retries = int(max_retries)
            
        if steroids is not None: 
            if self.asimod_steroids_var: self.asimod_steroids_var.set(bool(steroids))
            else: self._asimod_steroids = bool(steroids)
            
        if steroids_level is not None: 
            if self.asimod_steroids_level_var: self.asimod_steroids_level_var.set(int(steroids_level))
            else: self._asimod_steroids_level = int(steroids_level)
            
        self.check_auto_turn()
        return {"success": True}

    def announce_move_voice(self, r1, c1, r2, c2):
        """Genera una locución corta del movimiento en voz masculina (OPONENTE)."""
        if not self.config_service.get("audio_agent", True):
            return
            
        cols, rows = "abcdefgh", "87654321"
        move_text = f"{cols[c1]} {rows[r1]} a {cols[c2]} {rows[r2]}"
        
        v_srv = getattr(self.chat_service, 'voice_service', None)
        if not v_srv: return

        import threading
        # Lanzar en hilo inmediatamente para no bloquear el hilo de UI de Tkinter
        def run_announcement():
            try:
                import time
                time.sleep(0.35) # Delay ajustado
                v_srv.speak_text(move_text, voice_id=self.opponent_voice_id)
            except Exception as e:
                print(f"[Ajedrez-Voice] Error en hilo: {e}")
        
        threading.Thread(target=run_announcement, daemon=True).start()

def get_module_class(): return AjedrezModule
