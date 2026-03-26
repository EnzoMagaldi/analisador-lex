#include <stdio.h>
#include <ctype.h>
#include <string.h>

typedef struct token
{
    char simbol [20];
    char tipo; // se vai ser palavra reservada, constante, variavel, etc...

}token; // talvez fazer isos depois

void lexico2(FILE* arq) {
    char palavra[100];
    int i = 0;
    char c;

    while ((c = fgetc(arq)) != EOF){
        if (isalpha(c)) {
            palavra[i] = c;
            i++;
        }
        /*else if (i > 0) { 
            palavra[i] = '\0'; // Finaliza a string com o caractere nulo
            printf("Palavra encontrada: %s\n", palavra);
        }*/
        if(isspace(c)){
            palavra[i] = '\0';
            printf("Palavra encontrada: %s\n", palavra);
            break;
        }
    }
}

int main(){
    FILE* arquivoCOOL = fopen("teste.txt", "r");
    lexico(arquivoCOOL);

    return 0;
}