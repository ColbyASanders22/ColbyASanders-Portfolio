import java.util.Scanner;
/**
 * 3x3 basketball game
 * 
 * @author Colby
 */
class Player {
    private String name;
    private int height;

    /**
     * 
     * gets constructors
     */
    public Player(String name, int height) {
        this.name = name;
        this.height = height;
    }
/**
 * defines player class
 */
    public Player() {}

    /**
     * 
     * Gets the getters and setters
     */
    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public int getHeight() {
        return height;
    }

    public void setHeight(int height) {
        this.height = height;
    }

    /**
     * 
     * defines tostring method
     */
    public String toString() {
        return "Name: " + name + ", Height: " + height + " inches";
    }
}

/**
 * 
 * defines team class
 */
class Team {
    private Player[] myTeam;

    public Team() {
        myTeam = new Player[3];
    }

    public void add(Player player) {
        for (int i = 0; i < myTeam.length; i++) {
            if (myTeam[i] == null) {
                myTeam[i] = player;
                break;
            }
        }
    }
/**
 * 
 * gets average height
 */
    public int averageHeight() {
        int totalHeight = 0;
        int playerCount = 0;

        for (Player player : myTeam) {
            if (player != null) {
                totalHeight += player.getHeight();
                playerCount++;
            }
        }

        return playerCount > 0 ? totalHeight / playerCount : 0;
    }

   
    public String toString() {
        StringBuilder result = new StringBuilder("Number of players: ");
        int playerCount = 0;

        for (Player player : myTeam) {
            if (player != null) {
                result.append("\n").append(player.toString());
                playerCount++;
            }
        }

        if (playerCount == 0) {
            result.append("0");
        }

        return result.toString();
    }
}

/**
 * defines game class
 * 
 *
 */
public class Game {
    private static Scanner scanner = new Scanner(System.in);

    /**
     * 
     * defines static method
     */
    private static Team fillRoster() {
        Team team = new Team();

        for (int i = 0; i < 3; i++) {
            System.out.println("Enter team member " + (i + 1) + ": ");
            Player player = new Player();

            /**
             * scanner input lines
             */
            System.out.print("Name: ");
            player.setName(scanner.nextLine());

            System.out.print("Height: ");
            player.setHeight(Integer.parseInt(scanner.nextLine()));

            team.add(player);
        }

        return team;
    }
/**
 * 
 * scanner input lines and gets the average height
 */
    public static void main(String[] args) {
        System.out.println("Enter the home team:");
        Team home = fillRoster();
        System.out.println("\nEnter the visiting team:");
        Team visitor = fillRoster();

        int homeAverageHeight = home.averageHeight();
        int visitorAverageHeight = visitor.averageHeight();

        System.out.println("\nHome Team:");
        System.out.println(home);
        System.out.println("\nVisitor Team:");
        System.out.println(visitor);

        /**
         * put the correct answer to output
         */
        if (homeAverageHeight > visitorAverageHeight) {
            System.out.println("\nHome team has the taller average height.");
        } else if (homeAverageHeight < visitorAverageHeight) {
            System.out.println("\nVisitor team has the taller average height.");
        } else {
            System.out.println("\nBoth teams have the same average height.");
        }
    }
}