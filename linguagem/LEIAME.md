# Manezês

Uma linguagem imperativa com o sotaque da Ilha da Magia. Um programa é uma lista de funções (`pesca`) seguida do bloco principal (`ilha`).

```
pesca tainha fatorial(tainha n) {
  capaz (n <= 1) {
    traz 1;
  }
  traz n * fatorial(n - 1);
}

ilha Floripa {
  tainha quantas = 5;
  fala("fatorial:", fatorial(quantas));
}
```

## Palavras reservadas

| Manezês | Significado | Por quê |
|---|---|---|
| `ilha` | programa principal | a Ilha de Santa Catarina |
| `pesca` | declara função | a gente vai pescar um resultado |
| `traz` | retorno | "traz a tainha!" |
| `tainha` | tipo inteiro | peixe se conta por unidade |
| `berbigao` | tipo real | |
| `fofoca` | tipo cadeia (texto) | é o que mais circula na ilha |
| `tasounao` | tipo lógico | "tás ou não tás?" |
| `dazumbanda` | verdadeiro | "dazumbanda" = da melhor qualidade |
| `tastolo` | falso | "tás tolo?" |
| `capaz` / `ouentao` | se / senão (aceita `ouentao capaz`, o else-if) | "capaz!" |
| `segue` | enquanto | "segue reto toda vida" |
| `rema i de 1 ate n` | para (repetição contada) | de canoa |
| `fala(...)` | escrita | |
| `escuta(x)` | leitura | |
| `e`, `ou`, `nao` | operadores lógicos | |

## Tokens (`lexico.er`)

```
id: [a-zA-Z_]([a-zA-Z_]|[0-9])*
real: [0-9]+[.][0-9]+
num: [0-9]+
cadeia: "[a-zA-Z0-9,.!?:;_]*"
op_rel: <|<=|>|>=|==|!=
op_arit: [+*/%]|-
atrib: =
delim: [(){};,]
```

As palavras reservadas também casam com `id` e são separadas pela tabela de símbolos.

Os arquivos da linguagem usam só a notação básica do enunciado, para rodarem nos geradores dos outros grupos: sem comentários, sem referências `{nome}`, sem escapes com `\` (caracteres como `.`, `+`, `*`, `(` e `{` ficam dentro de classes, como `[.]` e `[(){};,]`) e sem espaço dentro de classe (muitos geradores removem os espaços da ER). Por isso, nos programas de exemplo, as cadeias usam `_` no lugar de espaço: `"tainha_da_sorte!"`.

## Sintaxe (`sintatico.glc`)

- Declaração: `tainha x;` ou `tainha x = expr;`
- Atribuição: `x = expr;`
- Chamada como comando: `f(a, b);`
- Condicional: `capaz (expr) { ... } ouentao capaz (expr) { ... } ouentao { ... }` (chaves obrigatórias, então não há "else pendente")
- Enquanto: `segue (expr) { ... }`
- Repetição: `rema i de expr ate expr { ... }`
- E/S: `fala(expr, expr, ...);` e `escuta(x);`
- Retorno: `traz expr;`
- Expressões, da menor para a maior precedência: `ou`, `e`, `nao`, relacionais (`< <= > >= == !=`, não associativos), `+ -`, `* / %`, menos unário, parênteses e chamadas de função.

A gramática tem 72 produções, gera 130 estados LR(0) e é SLR(1) sem nenhum conflito.

## Programas de teste

- `correto.mane`: usa todas as construções; é aceito.
- `com_erro.mane`: `capaz peixes > 5 {` sem os parênteses; erro sintático na linha 3, coluna 9 (esperado `(`).
- `com_erro_lexico.mane`: `peixes @ 2`; o `@` não é token (erro léxico na linha 3, coluna 19).
