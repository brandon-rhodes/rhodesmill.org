;; Brandon Craig Rhodes's Emacs initialization
;; (Or, at least, the excerpts from it relevant to using the
;;  Python packages Rope, Ropemacs, Pymacs, and PyFlakes.)

(add-to-list 'load-path "~/.emacs.d")

;; Run Pymacs using the Python virtualenv we build under .emacs.d.

(setenv "PYMACS_PYTHON" "~/.emacs.d/usr/bin/python2.5")

(autoload 'pymacs-apply "pymacs")
(autoload 'pymacs-call "pymacs")
(autoload 'pymacs-eval "pymacs" nil t)
(autoload 'pymacs-exec "pymacs" nil t)
(autoload 'pymacs-load "pymacs" nil t)

(require 'pymacs)

;; Load ropemacs, which depends on Pymacs (see above).

(pymacs-load "ropemacs" "rope-")

;; Set up Flymake to use PyFlakes.

(when (load "flymake" t)
  (defun flymake-pyflakes-init ()
    (let* ((temp-file (flymake-init-create-temp-buffer-copy
                       'flymake-create-temp-inplace))
           (local-file (file-relative-name
                        temp-file
                        (file-name-directory buffer-file-name))))
      (list "/home/brandon/.emacs.d/usr/bin/pyflakes" (list local-file))))
  
  (add-to-list 'flymake-allowed-file-name-masks
               '("\\.py\\'" flymake-pyflakes-init)))

(add-hook 'find-file-hook 'flymake-find-file-hook)

;; End.
