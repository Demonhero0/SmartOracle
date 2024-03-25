package main

import (
	"fmt"
	"os"

	cmd "github.com/ethereum/go-ethereum/hunter/cmd"
	"github.com/ethereum/go-ethereum/internal/flags"

	// cli "gopkg.in/urfave/cli.v1"
	cli "github.com/urfave/cli/v2"
)

var (
	gitCommit = "" // Git SHA1 commit hash of the release (set via linker flags)
	gitDate   = ""

	app                       = flags.NewApp("Ethereum substate command line interface")
	OriginCommandHelpTemplate = `{{.Name}}{{if .Subcommands}} command{{end}}{{if .Flags}} [command options]{{end}} {{.ArgsUsage}}
	{{if .Description}}{{.Description}}
	{{end}}{{if .Subcommands}}
	SUBCOMMANDS:
	  {{range .Subcommands}}{{.Name}}{{with .ShortName}}, {{.}}{{end}}{{ "\t" }}{{.Usage}}
	  {{end}}{{end}}{{if .Flags}}
	OPTIONS:
	{{range $.Flags}}   {{.}}
	{{end}}
	{{end}}`
)

func init() {
	app.Flags = []cli.Flag{}
	app.Commands = []*cli.Command{
		&cmd.ReplayCommand,
		&cmd.ReplayWithTxHashCommand,
		&cmd.ReplayBlockhCommand,
		&cmd.ReplayInvCommand,
	}
	cli.CommandHelpTemplate = OriginCommandHelpTemplate
}

func main() {
	if err := app.Run(os.Args); err != nil {
		code := 1
		fmt.Fprintln(os.Stderr, err)
		os.Exit(code)
	}
}
