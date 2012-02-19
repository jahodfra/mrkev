" Vim syntax file
" Language:	Mrkev language
" Maintainer:	Frantisek Jahoda <frantisek.jahoda@gmail.com>
" URL:		http://github.com/jahodfra/mrkev

if exists("b:current_syntax")
  finish
endif

syn case match

syn cluster markupBlockContent contains=markupBlock,markupComment,markupString,markupAlias
"markupScope,markupResolver,markupLink
"syn cluster markupBlockContentCss contains=markupBlock,markupComment,markupAlias,markupScope,markupResolver

"mark illegal characters
syn match markupError '[\[\]]'
syn match markupUnexpected contained '\w\+'

syn match markupString contained '[^\[\]]\+'
syn region markupComment matchgroup=markupComment start='\[\*' matchgroup=markupComment end='\*\]'
syn region markupBlock matchgroup=markupBlock start='\[[a-zA-Z0-9:.]\+' matchgroup=markupBlock end='\]' contains=markupArgument,markupUnexpected

syn region markupArgument contained matchgroup=markupArgument start='[a-zA-Z]\+=\[' matchgroup=markupArgument end='\]' contains=@markupBlockContent
syn region markupArgument contained matchgroup=markupArgument start='\['           matchgroup=markupArgument end='\]' contains=@markupBlockContent
syn region markupArgument contained matchgroup=markupDefinition start='[:]=\[' matchgroup=markupDefinition end='\]' contains=@markupBlockContent 

syn match markupAlias contained /\[@\]/

"css properties
"syn include @css syntax/css.vim
"syn cluster inlineCss contains=css.*Attr,css.*Prop,cssComment,cssValue.*,cssColor,cssURL,cssImportant,cssError,cssStringQ,cssStringQQ,cssFunction,cssUnicodeEscape
"syn region markupArgument contained matchgroup=markupArgument start=' \(\w\)*Style=\[' matchgroup=markupArgument end='\]' contains=@inlineCss,@markupBlockContentCss
"syn region markupArgument contained matchgroup=markupArgument start=' \(\w\)*Color=\[' matchgroup=markupArgument end='\]' contains=cssColor,cssError,cssUnicodeEscape

"syn region markupLink contained matchgroup=markupLink start='\[>[a-zA-Z0-9_.]*' matchgroup=markupLink end='\]' contains=markupArgument
"syn match markupScope contained /\[\$\w*\]/
"syn region markupResolver contained matchgroup=markupResolver start='\[#[a-zA-Z\.]*' matchgroup=markupResolver end='\]' contains=markupArgument

command! -nargs=+ HiLink hi def link <args>
HiLink markupError              Error
HiLink markupUnexpected         Error

HiLink markupBlock              Type

HiLink markupArgument           Identifier
HiLink markupString             String
HiLink markupDefinition         Statement
HiLink markupComment            Comment

HiLink markupAlias              Constant

"HiLink markupLink               Function
"HtmlHiLink markupResolver           Special
"HtmlHiLink markupScope              Function
delcommand HiLink
let b:current_syntax = "markup"

