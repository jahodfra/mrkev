" Vim syntax file
" Language:	Mrkev language
" Maintainer:	Frantisek Jahoda <frantisek.jahoda@gmail.com>
" URL:		http://github.com/jahodfra/mrkev

if exists("b:current_syntax")
  finish
endif

syn case match

syn cluster mrkevBlockContent contains=mrkevBlock,mrkevComment,mrkevString,mrkevParam,mrkevDefinition

"mark illegal characters
syn match mrkevError '[\[\]]'
syn match mrkevUnexpected contained '\w\+'

syn match mrkevString contained '[^\[\]]\+'
syn region mrkevBlock matchgroup=mrkevBlock start='\[[^\[\] ]\+' matchgroup=mrkevBlock end='\]' contains=mrkevArgument,mrkevUnexpected
syn region mrkevComment matchgroup=mrkevComment start='\[\*' matchgroup=mrkevComment end='\*\]'
syn region mrkevDefinition matchgroup=mrkevDefinition start='\[[^\[\] ]\+\s\+:=' matchgroup=mrkevDefinition end='\]' contains=mrkevArgument,mrkevUnexpected 

syn region mrkevArgument contained matchgroup=mrkevArgument start='[^=\[\] ]\+=\[' matchgroup=mrkevArgument end='\]' contains=@mrkevBlockContent
syn region mrkevArgument contained matchgroup=mrkevArgument start='\['           matchgroup=mrkevArgument end='\]' contains=@mrkevBlockContent
syn match mrkevParam /\[\$[a-zA-Z]\+\]/


command! -nargs=+ HiLink hi def link <args>
HiLink mrkevError              Error
HiLink mrkevUnexpected         Error

HiLink mrkevBlock              Normal

HiLink mrkevArgument           Identifier
HiLink mrkevString             String
HiLink mrkevDefinition         Identifier
HiLink mrkevComment            Comment

HiLink mrkevParam              Include
delcommand HiLink
let b:current_syntax = "mrkev"

