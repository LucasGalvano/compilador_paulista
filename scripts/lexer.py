#  Classe Token
class Token:
    def __init__(self, tipo: str, lexema: str, linha: int):
        self.tipo   = tipo
        self.lexema = lexema
        self.linha  = linha

    def __repr__(self):
        return f"<{self.tipo}, '{self.lexema}', linha {self.linha}>"



#  Palavras reservadas (verificadas antes de ID)
PALAVRAS_RESERVADAS = {
    # Estrutura do programa
    "bora"   : "PROG_START",
    "fechou" : "PROG_END",
    # Controle de fluxo
    "se"          : "IF",
    "sepa"        : "ELSEIF",
    "pa"          : "ELSE",
    "fazocorre"   : "WHILE",
    "peao"        : "FOR",
    # I/O
    "pprt"        : "PRINT",
    "mandaopapo"  : "INPUT",
    # Controle de laço
    "vaza"        : "BREAK",
    "segue"       : "CONTINUE",
    # Funções
    "missao"      : "FUNC",
    "volta"       : "RETURN",
    # Tipos
    "cheio"       : "INT_TYPE",
    "quebrada"    : "FLOAT_TYPE",
    "papo"        : "STRING_TYPE",
    # Booleanos
    "real"        : "TRUE",
    "fake"        : "FALSE",
}

#  Helpers de classificação de caracteres
def is_digit(c: str) -> bool:
    return '0' <= c <= '9'

def is_alpha(c: str) -> bool:
    return ('a' <= c <= 'z') or ('A' <= c <= 'Z')

def is_alnum(c: str) -> bool:
    return is_alpha(c) or is_digit(c)



#  Lexer
class Lexer:
    def __init__(self, codigo: str):
        self.codigo  = codigo
        self.pos     = 0
        self.linha   = 1
        self.tokens  = []
        self.erros   = []
        # guarda cada linha do fonte para exibir no erro
        self.linhas  = codigo.splitlines()

    # navegação no buffer 
    def atual(self) -> str:
        if self.pos < len(self.codigo):
            return self.codigo[self.pos]
        return '\0'

    def proximo(self) -> str:
        if self.pos + 1 < len(self.codigo):
            return self.codigo[self.pos + 1]
        return '\0'

    def avancar(self) -> str:
        c = self.atual()
        self.pos += 1
        if c == '\n':
            self.linha += 1
        return c

    def peek_word(self) -> str:
        """Lê a palavra a partir da posição atual sem consumir."""
        i = self.pos
        while i < len(self.codigo) and is_alnum(self.codigo[i]):
            i += 1
        return self.codigo[self.pos:i]

    # tokenização principal
    def tokenizar(self) -> list:
        while self.pos < len(self.codigo):
            c = self.atual()

            # Espaço, tab, retorno ignora
            if c in (' ', '\t', '\r'):
                self.avancar()
                continue

            # Quebra de linha ignora (linha já incrementada em avancar)
            if c == '\n':
                self.avancar()
                continue

            # Comentário: # até fim da linha
            if c == '#':
                self._ler_comentario()
                continue

            # String literal: "..."
            if c == '"':
                self._ler_string()
                continue

            # Número: inteiro ou decimal (FLOAT antes de INT)
            if is_digit(c):
                self._ler_numero()
                continue

            # Identificador ou palavra reservada
            if is_alpha(c):
                self._ler_palavra()
                continue

            # Operadores e delimitadores
            tok = self._ler_operador()
            if tok:
                self.tokens.append(tok)
                continue

            # Caractere desconhecido erro léxico
            self._erro_lexico(self.linha, f"caractere inesperado '{c}'")
            self.avancar()

        self.tokens.append(Token("EOF", "$", self.linha))
        return self.tokens

    # reconhecimento de comentário 

    def _erro_lexico(self, linha: int, msg: str, col: int = None):
        """Formata erro léxico com contexto visual."""
        cabecalho = f"Chapou aqui mano: linha {linha} — {msg}"
        if 1 <= linha <= len(self.linhas):
            trecho = self.linhas[linha - 1]
            # calcula coluna: posição atual dentro da linha
            if col is None:
                # conta chars até self.pos na linha atual
                inicio_linha = self.codigo.rfind('\n', 0, self.pos) + 1
                col = self.pos - inicio_linha
            setinha = ' ' * max(col, 0) + '^'
            self.erros.append(f"{cabecalho}\n    {trecho}\n    {setinha}")
        else:
            self.erros.append(cabecalho)

    # reconhecimento de comentário 

    def _ler_comentario(self):
        """# comentário até fim da linha"""
        while self.atual() not in ('\n', '\0'):
            self.avancar()

    # reconhecimento de string 

    def _ler_string(self):
        linha_inicio = self.linha
        self.avancar()  # consome "
        lexema = ''
        while self.atual() != '"' and self.atual() != '\0':
            lexema += self.avancar()
        if self.atual() == '"':
            self.avancar()  # consome "
            self.tokens.append(Token("STRING", f'"{lexema}"', linha_inicio))
        else:
            self._erro_lexico(linha_inicio, "string não fechada")

    # reconhecimento de número 
    def _ler_numero(self):
        linha_inicio = self.linha
        lexema = ''
        while is_digit(self.atual()):
            lexema += self.avancar()

        # FLOAT: tem ponto seguido de dígito
        if self.atual() == '.' and is_digit(self.proximo()):
            lexema += self.avancar()  # consome '.'
            while is_digit(self.atual()):
                lexema += self.avancar()
            self.tokens.append(Token("FLOAT_NUM", lexema, linha_inicio))
        else:
            self.tokens.append(Token("INT_NUM", lexema, linha_inicio))

    # reconhecimento de palavra / reservada 
    def _ler_palavra(self):
        linha_inicio = self.linha
        lexema = ''
        while is_alnum(self.atual()):
            lexema += self.avancar()

        # Verifica palavra reservada
        if lexema in PALAVRAS_RESERVADAS:
            self.tokens.append(Token(PALAVRAS_RESERVADAS[lexema], lexema, linha_inicio))
        else:
            self.tokens.append(Token("ID", lexema, linha_inicio))

    # reconhecimento de operadores 
    def _ler_operador(self) -> Token | None:
        linha = self.linha
        c = self.atual()
        n = self.proximo()

        # Dois caracteres  verificar ANTES dos de um caractere
        if c == '+' and n == '+':
            self.avancar(); self.avancar()
            return Token("INCREMENT", "++", linha)

        if c == '-' and n == '-':
            self.avancar(); self.avancar()
            return Token("DECREMENT", "--", linha)

        if c == '>' and n == '=':
            self.avancar(); self.avancar()
            return Token("GE", ">=", linha)

        if c == '<' and n == '=':
            self.avancar(); self.avancar()
            return Token("LE", "<=", linha)

        if c == '=' and n == '=':
            self.avancar(); self.avancar()
            return Token("EQ", "==", linha)

        if c == '!' and n == '=':
            self.avancar(); self.avancar()
            return Token("NE", "!=", linha)

        if c == '&' and n == '&':
            self.avancar(); self.avancar()
            return Token("AND", "&&", linha)

        if c == '|' and n == '|':
            self.avancar(); self.avancar()
            return Token("OR", "||", linha)

        # Um caractere
        mapa = {
            '+': "PLUS",
            '-': "MINUS",
            '*': "MULT",
            '/': "DIV",
            '>': "GT",
            '<': "LT",
            '=': "ASSIGN",
            '!': "NOT",
            '{': "LBRACE",
            '}': "RBRACE",
            '(': "LPAREN",
            ')': "RPAREN",
            ';': "SEMICOLON",
            ',': "COMMA",
        }

        if c in mapa:
            self.avancar()
            return Token(mapa[c], c, linha)

        return None



#  Função auxiliar: imprimir lista de tokens
def imprimir_tokens(tokens: list):
    print("\n══════════════════════════════════════")
    print("  LISTA DE TOKENS")
    print("══════════════════════════════════════")
    for tok in tokens:
        print(f"  {tok}")
    print("══════════════════════════════════════\n")



#  Ponto de entrada standalone
if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python lexer.py <arquivo.paulista>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        codigo = f.read()

    lexer = Lexer(codigo)
    tokens = lexer.tokenizar()

    imprimir_tokens(tokens)

    if lexer.erros:
        print("Erros léxicos encontrados:")
        for e in lexer.erros:
            print(" ", e)